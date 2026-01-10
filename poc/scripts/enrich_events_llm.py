#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 기반 이벤트 보강 스크립트

기능:
1. 이벤트 제목 정리 (title_clean)
2. 연도/시대 추출 및 수정
3. 위치 지오코딩
4. 유효성 검증 (이벤트 vs 기사)
5. 카테고리 재분류

사용법:
    # 테스트 모드 (10개)
    python enrich_events_llm.py --test 10

    # 전체 실행 (Batch API)
    python enrich_events_llm.py --full --batch

    # 결과 적용
    python enrich_events_llm.py --apply results/enrichment_YYYYMMDD.json
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from dotenv import load_dotenv
load_dotenv()

import openai
from openai import OpenAI

# Configuration
MODEL = "gpt-5.1-chat-latest"  # GPT-5.1 최신
RESULTS_DIR = Path(__file__).parent.parent / "data" / "enrichment_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# System prompt for event enrichment
SYSTEM_PROMPT = """You are a historical data enrichment expert. Your task is to analyze historical records and provide structured enrichment data.

For each record, determine:

1. **Record Type**: What kind of historical record is this?
   - "event": A specific historical occurrence (battle, treaty, coronation, revolution, etc.)
   - "article": An encyclopedic article or essay about a historical topic
   - "period": A historical period or era description
   - "concept": A concept, tradition, practice, or cultural phenomenon

2. **Title**: Clean up the title (remove article prefixes, truncated text, interview markers, etc.)

3. **Date/Era**: Even for articles, extract the time period it discusses
   - year_start: Start year (negative for BCE). For articles, use the START of the period discussed.
   - year_end: End year. For articles, use the END of the period discussed.
   - year_precision: "exact", "year", "decade", "century", "millennium"
   - For articles about long periods (e.g., "Women in Ancient Persia"), use approximate ranges like -550 to -330

4. **Era Classification**:
   - PREHISTORY: Before 3000 BCE
   - ANCIENT: 3000 BCE - 800 BCE
   - CLASSICAL: 800 BCE - 500 CE
   - MEDIEVAL: 500 CE - 1500 CE
   - EARLY_MODERN: 1500 CE - 1800 CE
   - MODERN: 1800 CE - 1945 CE
   - CONTEMPORARY: 1945 CE - present

5. **Location/Region**: Primary geographic focus
   - For events: exact location with coordinates
   - For articles: the region/civilization discussed (e.g., "Persia", "Mesoamerica")
   - confidence: "high", "medium", "low", "none"

6. **Category**:
   - battle, war, politics, religion, philosophy, science, culture, civilization, discovery, treaty, art, technology, other

7. **Civilization/Culture**: The primary civilization discussed (e.g., "Persian", "Maya", "Celtic", "Roman")

NOTE: Do NOT generate summaries. Summaries require multi-source aggregation and will be generated separately in the curation phase.

IMPORTANT RULES:
- For BCE dates, use NEGATIVE numbers (e.g., -490 for 490 BCE)
- ALWAYS extract era and region info, even for articles
- For articles about "Ancient X", estimate the time range of that civilization
- Clean up messy titles like "Interviewby James..." or truncated text
- Treaties, battles, wars, coronations ARE specific events
- General topic articles (e.g., "Women in Ancient Persia", "Celtic Bronze Shields") are articles but still have historical metadata

Respond in JSON format only."""

USER_PROMPT_TEMPLATE = """Analyze this historical record and provide enrichment data:

ID: {id}
Current Title: {title}
Current Year: {year}
Description (first 1000 chars): {description}
Source URL: {url}

Respond with a JSON object following this exact schema:
{{
  "id": {id},
  "record_type": "event" | "article" | "period" | "concept",

  "title_clean": "Cleaned English title",

  "year_start": -490,
  "year_end": -490,
  "year_precision": "exact" | "year" | "decade" | "century" | "millennium",
  "era": "CLASSICAL",
  "temporal_scale": "evenementielle" | "conjuncture" | "longue_duree",

  "location_name": "Historical/Ancient name",
  "location_modern": "Modern name, Country",
  "latitude": 38.123,
  "longitude": 23.456,
  "location_type": "city" | "battlefield" | "region" | "country" | "other",
  "location_confidence": "high" | "medium" | "low" | "none",

  "category": "battle",
  "civilization": "Persian" | "Greek" | "Roman" | "Maya" | "Celtic" | etc.,

  "confidence": "high" | "medium" | "low",
  "needs_review": false
}}"""


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


def load_events(limit: Optional[int] = None, offset: int = 0, event_ids: Optional[List[int]] = None, ner_only: bool = False) -> List[Dict]:
    """Load events from database."""
    conn = get_db_connection()
    cur = conn.cursor()

    if event_ids:
        # Load specific events
        placeholders = ','.join(['%s'] * len(event_ids))
        cur.execute(f'''
            SELECT id, title, description, date_start, wikipedia_url
            FROM events
            WHERE id IN ({placeholders})
            ORDER BY id
        ''', event_ids)
    elif ner_only:
        # Load only NER events (not yet enriched)
        cur.execute('''
            SELECT id, title, description, date_start, wikipedia_url
            FROM events
            WHERE slug LIKE 'ner-%%' AND enriched_by IS NULL
            ORDER BY id
            LIMIT %s OFFSET %s
        ''', (limit or 100000, offset))
    else:
        # Load with limit/offset
        cur.execute('''
            SELECT id, title, description, date_start, wikipedia_url
            FROM events
            ORDER BY id
            LIMIT %s OFFSET %s
        ''', (limit or 100000, offset))

    events = []
    for row in cur.fetchall():
        events.append({
            'id': row[0],
            'title': row[1] or '',
            'description': (row[2] or '')[:1000],  # Truncate description
            'year': row[3] or 0,
            'url': row[4] or ''
        })

    conn.close()
    return events


def enrich_event_sync(client: OpenAI, event: Dict, model: str = MODEL) -> Dict:
    """Enrich a single event using OpenAI API (synchronous)."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        id=event['id'],
        title=event['title'],
        year=event['year'],
        description=event['description'],
        url=event['url']
    )

    try:
        # GPT-5 series uses max_completion_tokens, older models use max_tokens
        if model.startswith('gpt-5'):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=1500
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )

        raw_content = response.choices[0].message.content
        if not raw_content or not raw_content.strip():
            return {
                'id': event['id'],
                'error': 'Empty response from model',
                'is_valid_event': None,
                'needs_review': True
            }

        # Try to extract JSON from markdown code blocks if present
        content = raw_content.strip()
        if content.startswith('```'):
            # Remove markdown code blocks
            lines = content.split('\n')
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith('```'):
                    in_block = not in_block
                    continue
                if in_block or not line.startswith('```'):
                    json_lines.append(line)
            content = '\n'.join(json_lines)

        result = json.loads(content)
        result['_tokens'] = {
            'input': response.usage.prompt_tokens,
            'output': response.usage.completion_tokens
        }
        return result

    except json.JSONDecodeError as e:
        return {
            'id': event['id'],
            'error': f'JSON parse error: {str(e)}',
            'raw_response': raw_content[:500] if 'raw_content' in dir() else 'N/A',
            'is_valid_event': None,
            'needs_review': True
        }
    except Exception as e:
        return {
            'id': event['id'],
            'error': str(e),
            'is_valid_event': None,
            'needs_review': True
        }


def create_batch_file(events: List[Dict], output_path: Path) -> Path:
    """Create JSONL file for Batch API."""
    jsonl_path = output_path.with_suffix('.jsonl')

    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for event in events:
            user_prompt = USER_PROMPT_TEMPLATE.format(
                id=event['id'],
                title=event['title'],
                year=event['year'],
                description=event['description'],
                url=event['url']
            )

            request = {
                "custom_id": f"event-{event['id']}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_completion_tokens": 1500
                }
            }
            f.write(json.dumps(request, ensure_ascii=False) + '\n')

    print(f"Created batch file: {jsonl_path}")
    return jsonl_path


def submit_batch(client: OpenAI, jsonl_path: Path) -> str:
    """Submit batch job to OpenAI."""
    # Upload file
    with open(jsonl_path, 'rb') as f:
        file_response = client.files.create(file=f, purpose='batch')

    print(f"Uploaded file: {file_response.id}")

    # Create batch
    batch_response = client.batches.create(
        input_file_id=file_response.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    print(f"Created batch: {batch_response.id}")
    print(f"Status: {batch_response.status}")

    return batch_response.id


def check_batch_status(client: OpenAI, batch_id: str) -> Dict:
    """Check batch job status."""
    batch = client.batches.retrieve(batch_id)
    return {
        'id': batch.id,
        'status': batch.status,
        'created_at': batch.created_at,
        'completed_at': batch.completed_at,
        'request_counts': batch.request_counts,
        'output_file_id': batch.output_file_id,
        'error_file_id': batch.error_file_id
    }


def download_batch_results(client: OpenAI, batch_id: str, output_path: Path) -> List[Dict]:
    """Download and parse batch results."""
    batch = client.batches.retrieve(batch_id)

    if batch.status != 'completed':
        print(f"Batch not completed. Status: {batch.status}")
        return []

    # Download output file
    output_file = client.files.content(batch.output_file_id)

    results = []
    for line in output_file.text.strip().split('\n'):
        item = json.loads(line)
        custom_id = item['custom_id']
        event_id = int(custom_id.replace('event-', ''))

        if item['response']['status_code'] == 200:
            content = item['response']['body']['choices'][0]['message']['content']
            result = json.loads(content)
            result['id'] = event_id
            results.append(result)
        else:
            results.append({
                'id': event_id,
                'error': item['response']['body'],
                'is_valid_event': None,
                'needs_review': True
            })

    # Save results
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} results to {output_path}")
    return results


def run_test(count: int = 10, model: str = MODEL):
    """Run test enrichment on a small batch."""
    print(f"\n=== 테스트 모드: {count}개 이벤트 (모델: {model}) ===\n")

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # Load diverse sample of events
    conn = get_db_connection()
    cur = conn.cursor()

    # Get a mix of different event types
    cur.execute('''
        (SELECT id FROM events WHERE date_start = 0 ORDER BY RANDOM() LIMIT %s)
        UNION ALL
        (SELECT id FROM events WHERE LENGTH(title) > 60 ORDER BY RANDOM() LIMIT %s)
        UNION ALL
        (SELECT id FROM events WHERE title LIKE 'Battle%%' ORDER BY RANDOM() LIMIT %s)
        UNION ALL
        (SELECT id FROM events WHERE title LIKE 'The %%' ORDER BY RANDOM() LIMIT %s)
        UNION ALL
        (SELECT id FROM events ORDER BY RANDOM() LIMIT %s)
    ''', (count//5 + 1, count//5 + 1, count//5 + 1, count//5 + 1, count//5 + 1))

    event_ids = list(set([row[0] for row in cur.fetchall()]))[:count]
    conn.close()

    events = load_events(event_ids=event_ids)
    print(f"로드된 이벤트: {len(events)}개\n")

    results = []
    total_input_tokens = 0
    total_output_tokens = 0

    for i, event in enumerate(events):
        print(f"[{i+1}/{len(events)}] ID {event['id']}: {event['title'][:50]}...")

        result = enrich_event_sync(client, event, model=model)
        results.append(result)

        if '_tokens' in result:
            total_input_tokens += result['_tokens']['input']
            total_output_tokens += result['_tokens']['output']

        # Print summary
        rtype = result.get('record_type', 'unknown')
        if result.get('error'):
            print(f"  [ERR] {str(result.get('error'))[:60]}")
        else:
            print(f"  [{rtype[:3].upper()}] {result.get('title_clean', 'N/A')[:45]}")
            year_str = f"{result.get('year_start', '?')}~{result.get('year_end', '')}" if result.get('year_end') else str(result.get('year_start', '?'))
            civ = result.get('civilization', '-')
            loc = (result.get('location_modern') or '-')[:25]
            print(f"       {year_str} | {civ} | {loc}")
        print()

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"test_{timestamp}.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'model': model,
                'count': len(results),
                'timestamp': timestamp,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'estimated_cost': (total_input_tokens * 0.005 + total_output_tokens * 0.015) / 1000
            },
            'results': results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n=== 결과 저장: {output_path} ===")
    print(f"토큰 사용: 입력 {total_input_tokens:,} / 출력 {total_output_tokens:,}")
    print(f"예상 비용: ${(total_input_tokens * 0.005 + total_output_tokens * 0.015) / 1000:.4f}")

    # Summary
    valid_events = sum(1 for r in results if r.get('is_valid_event'))
    invalid = sum(1 for r in results if r.get('is_valid_event') == False)
    errors = sum(1 for r in results if r.get('error'))

    print(f"\n=== 요약 ===")
    print(f"유효한 이벤트: {valid_events}개")
    print(f"이벤트 아님: {invalid}개")
    print(f"에러: {errors}개")

    return results


def run_full_batch():
    """Run full enrichment using Batch API."""
    print("\n=== 전체 Batch 모드 ===\n")
    print("NOTE: gpt-5.1-chat-latest는 Batch API를 지원하지 않습니다.")
    print("동기 모드(--full-sync)를 사용하세요.")
    return


def run_full_sync(workers: int = 5, resume_from: int = 0, ner_only: bool = False, model: str = MODEL):
    """Run full enrichment using concurrent API calls."""
    import concurrent.futures
    import time

    mode_str = "NER 이벤트" if ner_only else "전체"
    print(f"\n=== {mode_str} 동기 모드 (workers={workers}, model={model}) ===\n", flush=True)

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # Load events
    events = load_events(ner_only=ner_only)
    print(f"총 이벤트: {len(events):,}개", flush=True)

    if resume_from > 0:
        events = events[resume_from:]
        print(f"Resume from index {resume_from}, remaining: {len(events):,}개")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"full_sync_{timestamp}.json"

    results = []
    total_input = 0
    total_output = 0
    start_time = time.time()

    def process_event(event):
        return enrich_event_sync(client, event, model=model)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_event, e): e for e in events}
        completed = 0

        for future in concurrent.futures.as_completed(futures):
            event = futures[future]
            result = future.result()
            results.append(result)
            completed += 1

            if '_tokens' in result:
                total_input += result['_tokens']['input']
                total_output += result['_tokens']['output']

            # Progress update every 100
            if completed % 100 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed
                remaining = len(events) - completed
                eta_sec = remaining / rate if rate > 0 else 0
                print(f"[{completed:,}/{len(events):,}] {rate:.1f}/s, ETA: {eta_sec/60:.1f}min", flush=True)

    # Sort results by ID
    results.sort(key=lambda x: x.get('id', 0))

    # Calculate cost (gpt-5.1 pricing estimate)
    cost = (total_input / 1000 * 0.002) + (total_output / 1000 * 0.008)

    output_data = {
        'metadata': {
            'model': model,
            'count': len(events),
            'timestamp': timestamp,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'estimated_cost': cost,
            'elapsed_seconds': time.time() - start_time
        },
        'results': results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    error_count = sum(1 for r in results if 'error' in r)
    elapsed = time.time() - start_time

    print(f"\n=== 결과 저장: {output_path} ===")
    print(f"처리 시간: {elapsed/60:.1f}분")
    print(f"토큰 사용: 입력 {total_input:,} / 출력 {total_output:,}")
    print(f"예상 비용: ${cost:.2f}")
    print(f"성공: {len(results) - error_count:,}개, 에러: {error_count:,}개")


def main():
    parser = argparse.ArgumentParser(description='LLM 기반 이벤트 보강')
    parser.add_argument('--test', type=int, metavar='N', help='테스트 모드 (N개 이벤트)')
    parser.add_argument('--model', type=str, default='gpt-5.1-chat-latest',
                        help='사용할 모델 (gpt-5.1-chat-latest, gpt-5-mini, gpt-5-nano)')
    parser.add_argument('--full', action='store_true', help='전체 실행 (Batch API - gpt-5.1 미지원)')
    parser.add_argument('--full-sync', action='store_true', help='전체 실행 (동기 API)')
    parser.add_argument('--ner-only', action='store_true', help='NER 이벤트만 처리')
    parser.add_argument('--workers', type=int, default=5, help='동시 처리 수 (기본 5)')
    parser.add_argument('--resume', type=int, default=0, help='재시작 인덱스')
    parser.add_argument('--status', type=str, metavar='BATCH_ID', help='배치 상태 확인')
    parser.add_argument('--download', type=str, metavar='BATCH_ID', help='배치 결과 다운로드')
    parser.add_argument('--apply', type=str, metavar='JSON_FILE', help='결과를 DB에 적용')

    args = parser.parse_args()

    if args.test:
        run_test(args.test, model=args.model)
    elif args.full:
        run_full_batch()
    elif args.full_sync:
        run_full_sync(workers=args.workers, resume_from=args.resume, ner_only=args.ner_only, model=args.model)
    elif args.status:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        status = check_batch_status(client, args.status)
        print(json.dumps(status, indent=2, default=str))
    elif args.download:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = RESULTS_DIR / f"results_{timestamp}.json"
        download_batch_results(client, args.download, output_path)
    elif args.apply:
        print("DB 적용 기능은 아직 구현되지 않았습니다.")
        print("결과 파일을 검토한 후 적용 스크립트를 실행하세요.")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
