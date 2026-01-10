#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person 엔리치먼트 스크립트 (OpenAI API)

대상: mention_count >= 10 이면서 birth_year가 NULL인 인물
추출: birth_year, death_year, role, era

사용법:
    python enrich_persons_llm.py --test        # 10개 테스트
    python enrich_persons_llm.py --full        # 전체 실행
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from openai import OpenAI

# Configuration
RESULTS_DIR = Path(__file__).parent.parent / "data" / "enrichment_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = RESULTS_DIR / "persons_checkpoint.json"

MODEL = "gpt-5.1-chat-latest"
MAX_WORKERS = 20
BATCH_SIZE = 500


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def get_persons_to_enrich(limit=None):
    """Get persons needing enrichment."""
    conn = get_db_connection()
    cur = conn.cursor()

    query = '''
        SELECT id, name, role, era, mention_count
        FROM persons
        WHERE mention_count >= 3 AND birth_year IS NULL
        ORDER BY mention_count DESC
    '''
    if limit:
        query += f' LIMIT {limit}'

    cur.execute(query)
    persons = cur.fetchall()
    conn.close()

    return [{'id': p[0], 'name': p[1], 'role': p[2], 'era': p[3], 'mentions': p[4]} for p in persons]


def create_prompt(person):
    """Create prompt for person enrichment."""
    context = f"Name: {person['name']}"
    if person.get('role'):
        context += f"\nRole: {person['role']}"
    if person.get('era'):
        context += f"\nEra: {person['era']}"

    return f"""Identify this historical figure and provide their biographical data.

{context}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "birth_year": <integer or null if unknown>,
  "death_year": <integer or null if unknown>,
  "role": "<primary role/occupation>",
  "era": "<historical era, e.g. 'Ancient Greek', 'Renaissance', 'Victorian'>",
  "is_real_person": <true/false - false for fictional characters, generic titles, or non-persons>
}}

Important:
- Use negative numbers for BCE years (e.g., -490 for 490 BCE)
- If this is a fictional character, location, or generic title (like "Queen"), set is_real_person to false
- For real historical figures with uncertain dates, provide best estimates or null"""


def enrich_person(client, person):
    """Enrich a single person via OpenAI API."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a historian specializing in biographical data. Return only valid JSON."},
                {"role": "user", "content": create_prompt(person)}
            ],
            max_completion_tokens=500
        )

        content = response.choices[0].message.content.strip()

        # Clean JSON if wrapped in markdown
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        result = json.loads(content)
        result['id'] = person['id']
        result['name'] = person['name']

        return {
            'result': result,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens
        }
    except Exception as e:
        return {
            'result': {'id': person['id'], 'name': person['name'], 'error': str(e)},
            'input_tokens': 0,
            'output_tokens': 0
        }


def save_checkpoint(count, success, errors, input_tokens, output_tokens):
    """Save checkpoint for resume."""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({
            'count': count,
            'success': success,
            'errors': errors,
            'input': input_tokens,
            'output': output_tokens
        }, f)


def main():
    parser = argparse.ArgumentParser(description='Person 엔리치먼트')
    parser.add_argument('--test', action='store_true', help='10개 테스트')
    parser.add_argument('--full', action='store_true', help='전체 실행')
    parser.add_argument('--limit', type=int, help='처리할 최대 개수')

    args = parser.parse_args()

    if not args.test and not args.full:
        print("Usage:")
        print("  python enrich_persons_llm.py --test     # Test 10")
        print("  python enrich_persons_llm.py --full     # Full run")
        return

    limit = 10 if args.test else args.limit

    print(f"Starting (model={MODEL})...")

    # Get persons
    persons = get_persons_to_enrich(limit)
    print(f"Persons: {len(persons):,}")

    if not persons:
        print("No persons to enrich!")
        return

    # Initialize OpenAI client
    client = OpenAI()

    # Process
    results = []
    total_input = 0
    total_output = 0
    success = 0
    errors = 0

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_person, client, p): p for p in persons}

        for future in as_completed(futures):
            response = future.result()
            results.append(response['result'])
            total_input += response['input_tokens']
            total_output += response['output_tokens']

            if 'error' in response['result']:
                errors += 1
            else:
                success += 1

            processed = success + errors
            if processed % BATCH_SIZE == 0:
                print(f"{processed:,}/{len(persons):,} ({success:,} ok, {errors:,} err)")
                save_checkpoint(processed, success, errors, total_input, total_output)

    elapsed = time.time() - start_time

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = RESULTS_DIR / f"persons_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'total': len(persons),
                'success': success,
                'errors': errors,
                'input_tokens': total_input,
                'output_tokens': total_output,
                'elapsed_seconds': elapsed
            },
            'results': results
        }, f, ensure_ascii=False, indent=2)

    # Calculate cost
    # gpt-5.1: $2.50/1M input, $10/1M output
    cost = (total_input * 2.5 / 1_000_000) + (total_output * 10 / 1_000_000)

    print(f"\nDone! {success:,} ok, {errors:,} err")
    print(f"Tokens: {total_input:,} in, {total_output:,} out")
    print(f"Cost: ${cost:.2f}")
    print(f"Time: {elapsed/60:.1f} min")
    print(f"Saved: {output_file}")


if __name__ == '__main__':
    main()
