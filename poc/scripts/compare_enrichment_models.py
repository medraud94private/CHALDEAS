#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
엔리치먼트 모델 비교 테스트

동일한 이벤트에 대해 3개 모델 비교:
- gpt-5.1-chat-latest (OpenAI)
- gpt-5-nano (OpenAI)
- gemma2:9b-instruct-q4_0 (Ollama 로컬)

사용법:
    python compare_enrichment_models.py --count 10
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# Configuration
OLLAMA_URL = "http://localhost:11434"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "model_comparison"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# System prompt (same for all models)
SYSTEM_PROMPT = """You are a historical data enrichment expert. Analyze the record and provide structured data.

For each record, extract:
1. record_type: "event" | "article" | "period" | "concept"
2. title_clean: Cleaned English title
3. year_start: Start year (negative for BCE, e.g., -490 for 490 BCE)
4. year_end: End year (same as start if single year)
5. era: PREHISTORY | ANCIENT | CLASSICAL | MEDIEVAL | EARLY_MODERN | MODERN | CONTEMPORARY
6. location_name: Historical location name
7. location_modern: Modern location name with country
8. latitude: Decimal latitude
9. longitude: Decimal longitude
10. category: battle | war | politics | religion | philosophy | science | culture | other
11. civilization: Primary civilization (Persian, Greek, Roman, etc.)

IMPORTANT:
- BCE dates use NEGATIVE numbers (-490 = 490 BCE)
- Always provide coordinates if location is known
- Return ONLY valid JSON, no markdown

JSON format:
{
  "id": 123,
  "record_type": "event",
  "title_clean": "Battle of Marathon",
  "year_start": -490,
  "year_end": -490,
  "era": "CLASSICAL",
  "location_name": "Marathon",
  "location_modern": "Marathon, Greece",
  "latitude": 38.1,
  "longitude": 24.0,
  "category": "battle",
  "civilization": "Greek"
}"""

USER_PROMPT_TEMPLATE = """Analyze this historical record:

ID: {id}
Title: {title}
Current Year: {year}
Description: {description}

Return JSON only."""


def get_db_connection():
    """Get database connection."""
    import psycopg2
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def load_sample_events(count: int = 10) -> List[Dict]:
    """Load sample events - mix of V0 and NER."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Get mix of V0 events (various types) and NER events
    cur.execute('''
        (SELECT id, title, description, date_start FROM events
         WHERE slug NOT LIKE 'ner-%%' AND title LIKE 'Battle%%'
         ORDER BY RANDOM() LIMIT %s)
        UNION ALL
        (SELECT id, title, description, date_start FROM events
         WHERE slug NOT LIKE 'ner-%%' AND title NOT LIKE 'Battle%%'
         ORDER BY RANDOM() LIMIT %s)
        UNION ALL
        (SELECT id, title, description, date_start FROM events
         WHERE slug LIKE 'ner-%%'
         ORDER BY RANDOM() LIMIT %s)
    ''', (count // 3 + 1, count // 3 + 1, count // 3 + 1))

    events = []
    for row in cur.fetchall():
        events.append({
            'id': row[0],
            'title': row[1] or '',
            'description': (row[2] or '')[:500],
            'year': row[3] or 0
        })

    conn.close()
    return events[:count]


def enrich_openai(client: OpenAI, event: Dict, model: str) -> Dict:
    """Enrich using OpenAI API."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        id=event['id'],
        title=event['title'],
        year=event['year'],
        description=event['description'][:500]
    )

    start = time.time()

    try:
        if model.startswith('gpt-5'):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=800,
                temperature=0.1
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.1
            )

        elapsed = time.time() - start
        content = response.choices[0].message.content.strip()

        # Remove markdown if present
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(l for l in lines if not l.startswith('```'))

        result = json.loads(content)
        result['_meta'] = {
            'model': model,
            'elapsed_sec': round(elapsed, 2),
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens
        }
        return result

    except json.JSONDecodeError as e:
        return {
            'id': event['id'],
            'error': f'JSON parse error: {e}',
            'raw': content[:200] if 'content' in dir() else 'N/A',
            '_meta': {'model': model, 'elapsed_sec': time.time() - start}
        }
    except Exception as e:
        return {
            'id': event['id'],
            'error': str(e),
            '_meta': {'model': model, 'elapsed_sec': time.time() - start}
        }


def enrich_ollama(event: Dict, model: str = "gemma2:9b-instruct-q4_0") -> Dict:
    """Enrich using Ollama local model."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        id=event['id'],
        title=event['title'],
        year=event['year'],
        description=event['description'][:500]
    )

    # Combined prompt for Ollama
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    start = time.time()

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 800
                }
            },
            timeout=120
        )

        elapsed = time.time() - start

        if resp.status_code != 200:
            return {
                'id': event['id'],
                'error': f'HTTP {resp.status_code}',
                '_meta': {'model': model, 'elapsed_sec': elapsed}
            }

        content = resp.json().get('response', '').strip()

        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            result['_meta'] = {
                'model': model,
                'elapsed_sec': round(elapsed, 2)
            }
            return result
        else:
            return {
                'id': event['id'],
                'error': 'No JSON found',
                'raw': content[:300],
                '_meta': {'model': model, 'elapsed_sec': elapsed}
            }

    except json.JSONDecodeError as e:
        return {
            'id': event['id'],
            'error': f'JSON parse error: {e}',
            '_meta': {'model': model, 'elapsed_sec': time.time() - start}
        }
    except Exception as e:
        return {
            'id': event['id'],
            'error': str(e),
            '_meta': {'model': model, 'elapsed_sec': time.time() - start}
        }


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except:
        return False


def compare_results(event: Dict, results: Dict[str, Dict]) -> Dict:
    """Compare results from different models."""
    comparison = {
        'event_id': event['id'],
        'original_title': event['title'],
        'original_year': event['year'],
        'models': {}
    }

    for model_name, result in results.items():
        model_data = {
            'title_clean': result.get('title_clean', 'N/A'),
            'year_start': result.get('year_start'),
            'record_type': result.get('record_type', 'N/A'),
            'category': result.get('category', 'N/A'),
            'location': result.get('location_modern', 'N/A'),
            'elapsed_sec': result.get('_meta', {}).get('elapsed_sec', 0),
            'error': result.get('error')
        }
        comparison['models'][model_name] = model_data

    return comparison


def main():
    parser = argparse.ArgumentParser(description='엔리치먼트 모델 비교')
    parser.add_argument('--count', type=int, default=10, help='테스트 이벤트 수')
    args = parser.parse_args()

    print("=" * 70)
    print("엔리치먼트 모델 비교 테스트")
    print("=" * 70)

    # Check Ollama
    ollama_available = check_ollama()
    if not ollama_available:
        print("[WARN] Ollama not running. Skipping gemma2 test.")

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # Load sample events
    events = load_sample_events(args.count)
    print(f"\nLoaded {len(events)} events for testing\n")

    # Models to test
    models = {
        'gpt-5.1': lambda e: enrich_openai(client, e, 'gpt-5.1'),
        'gpt-5-nano': lambda e: enrich_openai(client, e, 'gpt-5-nano'),
    }

    if ollama_available:
        models['gemma2:9b'] = lambda e: enrich_ollama(e, 'gemma2:9b-instruct-q4_0')

    all_results = []
    comparisons = []

    for i, event in enumerate(events):
        print(f"\n[{i+1}/{len(events)}] ID {event['id']}: {event['title'][:50]}...")
        print(f"    Original year: {event['year']}")

        event_results = {}

        for model_name, enrich_fn in models.items():
            print(f"    Testing {model_name}...", end=' ', flush=True)
            result = enrich_fn(event)
            event_results[model_name] = result

            if result.get('error'):
                print(f"ERROR: {result['error'][:40]}")
            else:
                elapsed = result.get('_meta', {}).get('elapsed_sec', 0)
                year = result.get('year_start', '?')
                title = result.get('title_clean', 'N/A')[:30]
                print(f"OK ({elapsed:.1f}s) year={year}, title={title}")

        all_results.append({
            'event': event,
            'results': event_results
        })
        comparisons.append(compare_results(event, event_results))

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for model_name in models.keys():
        times = [r['results'].get(model_name, {}).get('_meta', {}).get('elapsed_sec', 0)
                 for r in all_results if not r['results'].get(model_name, {}).get('error')]
        errors = sum(1 for r in all_results if r['results'].get(model_name, {}).get('error'))

        if times:
            avg_time = sum(times) / len(times)
            print(f"\n{model_name}:")
            print(f"  Success: {len(times)}/{len(events)}")
            print(f"  Errors: {errors}")
            print(f"  Avg time: {avg_time:.2f}s")

            if 'gpt-5' in model_name:
                # Estimate cost
                tokens = [r['results'].get(model_name, {}).get('_meta', {}) for r in all_results]
                total_in = sum(t.get('input_tokens', 0) for t in tokens)
                total_out = sum(t.get('output_tokens', 0) for t in tokens)

                if 'nano' in model_name:
                    cost = (total_in * 0.0001 + total_out * 0.0004) / 1000
                else:
                    cost = (total_in * 0.002 + total_out * 0.008) / 1000

                print(f"  Tokens: {total_in:,} in / {total_out:,} out")
                print(f"  Cost: ${cost:.4f}")
                print(f"  Est. 41K events: ${cost/len(events)*41241:.2f}")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"comparison_{timestamp}.json"

    output_data = {
        'metadata': {
            'timestamp': timestamp,
            'event_count': len(events),
            'models_tested': list(models.keys())
        },
        'comparisons': comparisons,
        'raw_results': all_results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n결과 저장: {output_path}")

    # Print comparison table
    print("\n" + "=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)

    for comp in comparisons:
        print(f"\nEvent {comp['event_id']}: {comp['original_title'][:40]}...")
        print(f"  Original year: {comp['original_year']}")
        for model_name, data in comp['models'].items():
            if data.get('error'):
                print(f"  {model_name[:15]:15} ERROR: {data['error'][:30]}")
            else:
                print(f"  {model_name[:15]:15} year={data['year_start']:>6} | {data['title_clean'][:25]:25} | {data['elapsed_sec']:.1f}s")


if __name__ == '__main__':
    main()
