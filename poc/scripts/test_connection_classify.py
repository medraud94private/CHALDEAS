#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Connection Type Classification - Model Comparison Test

다양한 모델로 연결 유형 분류 테스트
- gpt-5.1-chat-latest
- gpt-5-mini
- gpt-5-nano
- 로컬 모델 (gemma2:9b)
"""

import sys
import json
import time
import os
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
import requests
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

OLLAMA_URL = "http://localhost:11434"

CLASSIFICATION_PROMPT_FULL = """Classify the relationship between two historical events.

Examples:
Event A: Storming of the Bastille (1789)
Event B: Execution of Louis XVI (1793)
Answer: {{"type": "leads_to", "confidence": 0.95}}

Event A: Battle of Lexington (1775)
Event B: Battle of Concord (1775)
Answer: {{"type": "part_of", "confidence": 0.98}}

Event A: Declaration of Independence (1776)
Event B: French Revolution (1789)
Answer: {{"type": "related", "confidence": 0.7}}

Types: causes, leads_to, follows, part_of, concurrent, related

Now classify:
Event A: {event_a_title} ({event_a_year})
Event B: {event_b_title} ({event_b_year})
Answer:"""

# 간단한 프롬프트 (mini/nano용)
CLASSIFICATION_PROMPT_SIMPLE = """Event A: {event_a_title} ({event_a_year})
Event B: {event_b_title} ({event_b_year})

What is the relationship? Reply ONLY with JSON: {{"type": "X", "confidence": 0.Y}}
Types: causes, leads_to, follows, part_of, concurrent, related"""


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


def get_sample_connections(n=5):
    """강한 연결 샘플 추출"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT
            ec.id,
            ec.strength_score,
            ec.source_count,
            ea.title as event_a_title,
            ea.date_start as event_a_year,
            eb.title as event_b_title,
            eb.date_start as event_b_year
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        WHERE ec.strength_score >= 30
        ORDER BY RANDOM()
        LIMIT %s
    ''', (n,))

    samples = []
    for row in cur.fetchall():
        samples.append({
            'id': row[0],
            'strength': row[1],
            'source_count': row[2],
            'event_a_title': row[3],
            'event_a_year': row[4],
            'event_b_title': row[5],
            'event_b_year': row[6],
        })

    conn.close()
    return samples


def classify_openai(client, sample, model):
    """OpenAI 모델로 분류"""
    # 모델별 프롬프트 선택
    prompt_template = CLASSIFICATION_PROMPT_SIMPLE if model in ['gpt-5-mini', 'gpt-5-nano'] else CLASSIFICATION_PROMPT_FULL
    prompt = prompt_template.format(
        event_a_title=sample['event_a_title'],
        event_a_year=sample['event_a_year'],
        event_b_title=sample['event_b_title'],
        event_b_year=sample['event_b_year'],
    )

    start = time.time()
    try:
        # 모델별 API 호출 - mini/nano는 시스템 메시지 없이
        if model in ['gpt-5-mini', 'gpt-5-nano']:
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = [
                {"role": "system", "content": "You are a historian. Respond with JSON only."},
                {"role": "user", "content": prompt}
            ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=300
        )
        elapsed = time.time() - start
        content = response.choices[0].message.content or ""

        # Parse JSON
        import re
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'success': True,
                'type': result.get('type'),
                'confidence': result.get('confidence'),
                'time': elapsed,
                'tokens_in': response.usage.prompt_tokens,
                'tokens_out': response.usage.completion_tokens,
            }
        return {'success': False, 'error': 'No JSON', 'raw': content[:100] if content else '(empty)', 'time': elapsed}
    except Exception as e:
        return {'success': False, 'error': str(e), 'time': time.time() - start}


def classify_ollama(sample, model="gemma2:9b"):
    """로컬 Ollama 모델로 분류"""
    prompt = CLASSIFICATION_PROMPT_FULL.format(
        event_a_title=sample['event_a_title'],
        event_a_year=sample['event_a_year'],
        event_b_title=sample['event_b_title'],
        event_b_year=sample['event_b_year'],
    )

    start = time.time()
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": f"You are a historian. Respond with JSON only.\n\n{prompt}",
                "stream": False,
                "options": {"num_predict": 100}
            },
            timeout=60
        )
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {'success': False, 'error': f'HTTP {resp.status_code}', 'time': elapsed}

        content = resp.json().get('response', '')

        import re
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'success': True,
                'type': result.get('type'),
                'confidence': result.get('confidence'),
                'time': elapsed,
                'tokens_in': 0,
                'tokens_out': 0,
            }
        return {'success': False, 'error': 'No JSON', 'raw': content[:100] if content else '(empty)', 'time': elapsed}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'Ollama not running', 'time': 0}
    except Exception as e:
        return {'success': False, 'error': str(e), 'time': time.time() - start}


def main():
    print("=" * 70)
    print("CONNECTION TYPE CLASSIFICATION - MODEL COMPARISON")
    print("=" * 70)

    # 샘플 추출
    print("\n[1] Fetching samples (strength >= 30)...")
    samples = get_sample_connections(5)
    print(f"Got {len(samples)} samples")

    for i, s in enumerate(samples):
        print(f"\n  Sample {i+1}:")
        print(f"    A: {s['event_a_title'][:50]}... ({s['event_a_year']})")
        print(f"    B: {s['event_b_title'][:50]}... ({s['event_b_year']})")
        print(f"    Strength: {s['strength']:.1f}, Sources: {s['source_count']}")

    # 모델 테스트
    models = [
        ('gpt-5.1-chat-latest', 'openai'),
        ('gpt-5-mini', 'openai'),
        ('gpt-5-nano', 'openai'),
        ('gemma2:9b', 'ollama'),
    ]

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    results = {model: [] for model, _ in models}

    print("\n[2] Testing models...")

    for model, provider in models:
        print(f"\n  === {model} ===")

        for i, sample in enumerate(samples):
            if provider == 'openai':
                result = classify_openai(client, sample, model)
            else:
                result = classify_ollama(sample, model)

            results[model].append(result)

            if result['success']:
                print(f"    Sample {i+1}: {result['type']} (conf: {result['confidence']}) [{result['time']:.2f}s]")
            else:
                raw = result.get('raw', '')
                print(f"    Sample {i+1}: ERROR - {result['error']}" + (f" | Raw: {raw}" if raw else ""))

    # 결과 요약
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n{'Model':<25} {'Success':<10} {'Avg Time':<12} {'Types'}")
    print("-" * 70)

    for model, _ in models:
        model_results = results[model]
        successes = [r for r in model_results if r['success']]
        success_rate = len(successes) / len(model_results) * 100
        avg_time = sum(r['time'] for r in model_results) / len(model_results)
        types = [r.get('type', '?') for r in successes]

        print(f"{model:<25} {success_rate:>5.0f}%     {avg_time:>6.2f}s     {types}")

    # 모델 간 일치도
    print("\n[Agreement Analysis]")
    for i in range(len(samples)):
        types = []
        for model, _ in models:
            r = results[model][i]
            types.append(r.get('type', 'ERROR') if r['success'] else 'ERROR')

        unique = set(types)
        agreement = "AGREE" if len(unique) == 1 else f"DIFFER ({unique})"
        print(f"  Sample {i+1}: {agreement}")


if __name__ == '__main__':
    main()
