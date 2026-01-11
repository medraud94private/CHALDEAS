#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Connection Type Classification - Batch Processor

Causal 체인의 connection_type을 LLM으로 분류
- 대상: strength_score >= 10, connection_type IS NULL
- 모델: gpt-5.1-chat-latest
"""

import sys
import json
import time
import re
import os
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

CLASSIFICATION_PROMPT = """Event A: {event_a_title} ({event_a_year})
Event B: {event_b_title} ({event_b_year})

Classify: causes/leads_to/follows/part_of/concurrent/related
Reply JSON only: {{"type":"X","confidence":0.Y}}"""


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


def get_pending_connections(conn, limit=None):
    """분류 필요한 연결 조회"""
    cur = conn.cursor()

    query = '''
        SELECT
            ec.id,
            ec.strength_score,
            ea.title as event_a_title,
            ea.date_start as event_a_year,
            eb.title as event_b_title,
            eb.date_start as event_b_year
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        WHERE ec.connection_type IS NULL
          AND ec.strength_score >= 10
        ORDER BY ec.strength_score DESC
    '''

    if limit:
        query += f' LIMIT {limit}'

    cur.execute(query)
    return cur.fetchall()


def classify_connection(client, event_a_title, event_a_year, event_b_title, event_b_year):
    """단일 연결 분류"""
    prompt = CLASSIFICATION_PROMPT.format(
        event_a_title=event_a_title[:100],  # Truncate long titles
        event_a_year=event_a_year,
        event_b_title=event_b_title[:100],
        event_b_year=event_b_year,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-5.1-chat-latest",
            messages=[
                {"role": "system", "content": "You are a historian. Respond with JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=100
        )

        content = response.choices[0].message.content or ""

        # Parse JSON
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'success': True,
                'type': result.get('type'),
                'confidence': result.get('confidence'),
                'tokens_in': response.usage.prompt_tokens,
                'tokens_out': response.usage.completion_tokens,
            }

        return {'success': False, 'error': 'No JSON in response'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def update_connection(conn, connection_id, connection_type, confidence):
    """연결 유형 업데이트"""
    cur = conn.cursor()
    cur.execute('''
        UPDATE event_connections
        SET connection_type = %s,
            verification_status = 'llm_verified',
            verified_by = 'gpt-5.1-chat-latest',
            verified_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
    ''', (connection_type, connection_id))
    conn.commit()


def main():
    print("=" * 60)
    print("CONNECTION TYPE CLASSIFICATION")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = get_db_connection()
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # 대상 조회
    print("\n[1] Fetching pending connections...")
    connections = get_pending_connections(conn)
    total = len(connections)
    print(f"Found {total:,} connections to classify")

    if total == 0:
        print("Nothing to classify!")
        return

    # 분류 시작
    print("\n[2] Classifying...")

    success_count = 0
    error_count = 0
    total_tokens_in = 0
    total_tokens_out = 0
    type_counts = {}

    start_time = time.time()

    for i, row in enumerate(connections):
        conn_id, strength, event_a_title, event_a_year, event_b_title, event_b_year = row

        result = classify_connection(
            client,
            event_a_title, event_a_year,
            event_b_title, event_b_year
        )

        if result['success']:
            conn_type = result['type']
            confidence = result['confidence']

            update_connection(conn, conn_id, conn_type, confidence)

            success_count += 1
            total_tokens_in += result['tokens_in']
            total_tokens_out += result['tokens_out']
            type_counts[conn_type] = type_counts.get(conn_type, 0) + 1

            # Progress every 50
            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                remaining = (total - i - 1) / rate if rate > 0 else 0
                print(f"  [{i+1}/{total}] {conn_type} | Rate: {rate:.1f}/s | ETA: {remaining/60:.1f}m")
        else:
            error_count += 1
            if error_count <= 5:  # Show first 5 errors
                print(f"  ERROR [{conn_id}]: {result['error'][:50]}")

        # Rate limiting - avoid hitting API limits
        time.sleep(0.1)

    elapsed = time.time() - start_time

    # 결과 요약
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total: {total:,}")
    print(f"Success: {success_count:,} ({success_count/total*100:.1f}%)")
    print(f"Errors: {error_count:,}")
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"Rate: {total/elapsed:.1f} connections/s")

    print(f"\nTokens used:")
    print(f"  Input: {total_tokens_in:,}")
    print(f"  Output: {total_tokens_out:,}")

    cost_in = total_tokens_in * 0.003 / 1000
    cost_out = total_tokens_out * 0.015 / 1000
    print(f"  Estimated cost: ${cost_in + cost_out:.2f}")

    print(f"\nType distribution:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c:,} ({c/success_count*100:.1f}%)")

    conn.close()
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
