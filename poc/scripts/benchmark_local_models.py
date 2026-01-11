#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
로컬 모델 벤치마크 스크립트

GPT-5.1-chat-latest와 로컬 모델(Ollama)의 엔리치먼트 품질/속도 비교

사용법:
    # 전체 모델 벤치마크
    python benchmark_local_models.py

    # 특정 모델만
    python benchmark_local_models.py --model llama3.1:8b-instruct-q4_0

    # GPT-5.1 포함 비교
    python benchmark_local_models.py --include-gpt
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from dotenv import load_dotenv
load_dotenv()

import requests

# Ollama 설정
OLLAMA_URL = "http://localhost:11434"

# 테스트할 로컬 모델들
LOCAL_MODELS = [
    "llama3.1:8b-instruct-q4_0",
    "mistral:7b-instruct-q4_0",
    "gemma2:9b-instruct-q4_0",
    "phi3:mini",
    "qwen3:1.7b",  # 작은 모델, 빠름
    "qwen3:4b",    # 중간 모델
]

# 결과 저장 디렉토리
RESULTS_DIR = Path(__file__).parent.parent / "data" / "benchmark_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 엔리치먼트 프롬프트 (enrich_events_llm.py와 동일)
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
   - For articles: the region/civilization discussed
   - confidence: "high", "medium", "low", "none"

6. **Category**:
   - battle, war, politics, religion, philosophy, science, culture, civilization, discovery, treaty, art, technology, other

7. **Civilization/Culture**: The primary civilization discussed

IMPORTANT RULES:
- For BCE dates, use NEGATIVE numbers (e.g., -490 for 490 BCE)
- ALWAYS extract era and region info
- Clean up messy titles

Respond in JSON format only. No markdown code blocks."""

USER_PROMPT_TEMPLATE = """Analyze this historical record and provide enrichment data:

ID: {id}
Current Title: {title}
Current Year: {year}
Description (first 500 chars): {description}

Respond with a JSON object:
{{
  "id": {id},
  "record_type": "event" | "article" | "period" | "concept",
  "title_clean": "Cleaned title",
  "year_start": -490,
  "year_end": -490,
  "year_precision": "exact" | "year" | "decade" | "century",
  "era": "CLASSICAL",
  "location_name": "Ancient name",
  "location_modern": "Modern name, Country",
  "latitude": 38.123,
  "longitude": 23.456,
  "category": "battle",
  "civilization": "Greek",
  "confidence": "high" | "medium" | "low"
}}"""


# GPT-5.1 테스트와 동일한 이벤트 ID (직접 비교용)
GPT_TEST_EVENT_IDS = [295, 1676, 2316, 6212, 9256]

# 기존 GPT-5.1 결과 파일 경로
GPT_BASELINE_FILE = Path(__file__).parent.parent / "data" / "enrichment_results" / "test_20260108_012319.json"


def load_events_from_db(event_ids: List[int]) -> List[Dict]:
    """DB에서 특정 이벤트 로드"""
    import psycopg2

    conn = psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )
    cur = conn.cursor()

    placeholders = ','.join(['%s'] * len(event_ids))
    cur.execute(f'''
        SELECT id, title, description, date_start, wikipedia_url
        FROM events
        WHERE id IN ({placeholders})
        ORDER BY id
    ''', event_ids)

    events = []
    for row in cur.fetchall():
        events.append({
            'id': row[0],
            'title': row[1] or '',
            'description': (row[2] or '')[:500],
            'year': row[3] or 0,
            'url': row[4] or ''
        })

    conn.close()
    return events


def load_gpt_baseline() -> Dict[int, Dict]:
    """기존 GPT-5.1 테스트 결과 로드"""
    if not GPT_BASELINE_FILE.exists():
        return {}

    with open(GPT_BASELINE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {r['id']: r for r in data.get('results', [])}


def check_ollama_running() -> bool:
    """Ollama 서버 상태 확인"""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except:
        return False


def get_available_models() -> List[str]:
    """Ollama에서 사용 가능한 모델 목록 조회"""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [m['name'] for m in data.get('models', [])]
    except:
        pass
    return []


def run_ollama_inference(model: str, event: Dict) -> Dict[str, Any]:
    """Ollama로 단일 이벤트 엔리치먼트 실행"""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        id=event['id'],
        title=event['title'],
        year=event['year'],
        description=event['description'][:500]
    )

    # Qwen3는 thinking mode 비활성화 필요
    options = {
        "temperature": 0.1,
        "num_predict": 1000
    }

    # Qwen3 thinking mode 비활성화: /nothink 접미사 또는 옵션
    if 'qwen3' in model.lower():
        user_prompt = user_prompt + "\n\n/nothink"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": options
    }

    start_time = time.time()

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=120
        )
        elapsed = time.time() - start_time

        if resp.status_code != 200:
            return {
                "id": event['id'],
                "error": f"HTTP {resp.status_code}",
                "elapsed_sec": elapsed
            }

        data = resp.json()
        content = data.get('message', {}).get('content', '')

        # 토큰 정보
        eval_count = data.get('eval_count', 0)
        prompt_eval_count = data.get('prompt_eval_count', 0)

        # JSON 파싱 시도
        try:
            # 마크다운 코드블록 제거
            clean_content = content.strip()
            if clean_content.startswith('```'):
                lines = clean_content.split('\n')
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith('```'):
                        in_block = not in_block
                        continue
                    json_lines.append(line)
                clean_content = '\n'.join(json_lines)

            result = json.loads(clean_content)
            result['_meta'] = {
                'elapsed_sec': elapsed,
                'input_tokens': prompt_eval_count,
                'output_tokens': eval_count,
                'tokens_per_sec': eval_count / elapsed if elapsed > 0 else 0
            }
            return result

        except json.JSONDecodeError as e:
            return {
                "id": event['id'],
                "error": f"JSON parse error: {e}",
                "raw_response": content[:300],
                "elapsed_sec": elapsed
            }

    except requests.exceptions.Timeout:
        return {
            "id": event['id'],
            "error": "Timeout (120s)",
            "elapsed_sec": 120
        }
    except Exception as e:
        return {
            "id": event['id'],
            "error": str(e),
            "elapsed_sec": time.time() - start_time
        }


def run_gpt_inference(event: Dict) -> Dict[str, Any]:
    """GPT-5.1-chat-latest로 단일 이벤트 엔리치먼트 실행"""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    user_prompt = USER_PROMPT_TEMPLATE.format(
        id=event['id'],
        title=event['title'],
        year=event['year'],
        description=event['description'][:500]
    )

    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model="gpt-5.1-chat-latest",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=1000,
            temperature=0.1
        )
        elapsed = time.time() - start_time

        content = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        # JSON 파싱
        try:
            clean_content = content.strip()
            if clean_content.startswith('```'):
                lines = clean_content.split('\n')
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith('```'):
                        in_block = not in_block
                        continue
                    json_lines.append(line)
                clean_content = '\n'.join(json_lines)

            result = json.loads(clean_content)
            result['_meta'] = {
                'elapsed_sec': elapsed,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'tokens_per_sec': output_tokens / elapsed if elapsed > 0 else 0
            }
            return result

        except json.JSONDecodeError as e:
            return {
                "id": event['id'],
                "error": f"JSON parse error: {e}",
                "raw_response": content[:300],
                "elapsed_sec": elapsed
            }

    except Exception as e:
        return {
            "id": event['id'],
            "error": str(e),
            "elapsed_sec": time.time() - start_time
        }


def benchmark_model(model: str, events: List[Dict], is_gpt: bool = False) -> Dict[str, Any]:
    """단일 모델 벤치마크 실행"""
    print(f"\n{'='*60}")
    print(f"모델: {model}")
    print(f"{'='*60}")

    results = []
    total_elapsed = 0
    total_output_tokens = 0
    errors = 0

    for i, event in enumerate(events):
        print(f"  [{i+1}/{len(events)}] {event['title'][:40]}...", end=" ", flush=True)

        if is_gpt:
            result = run_gpt_inference(event)
        else:
            result = run_ollama_inference(model, event)

        results.append(result)

        if 'error' in result:
            print(f"[ERR] {result['error'][:30]}")
            errors += 1
        else:
            meta = result.get('_meta', {})
            elapsed = meta.get('elapsed_sec', result.get('elapsed_sec', 0))
            tps = meta.get('tokens_per_sec', 0)
            total_elapsed += elapsed
            total_output_tokens += meta.get('output_tokens', 0)
            print(f"[OK] {elapsed:.1f}s, {tps:.1f} tok/s")

    avg_time = total_elapsed / len(events) if events else 0
    avg_tps = total_output_tokens / total_elapsed if total_elapsed > 0 else 0

    summary = {
        'model': model,
        'total_events': len(events),
        'errors': errors,
        'success_rate': (len(events) - errors) / len(events) * 100 if events else 0,
        'total_elapsed_sec': total_elapsed,
        'avg_time_per_event': avg_time,
        'avg_tokens_per_sec': avg_tps,
        'results': results
    }

    print(f"\n  요약: 성공률 {summary['success_rate']:.0f}%, 평균 {avg_time:.1f}s/이벤트, {avg_tps:.1f} tok/s")

    return summary


def compare_quality(benchmarks: Dict[str, Dict], gpt_baseline: Dict[int, Dict] = None) -> Dict[str, Any]:
    """모델간 품질 비교 (GPT-5.1을 기준으로)"""
    # GPT 베이스라인이 없으면 benchmarks에서 찾기
    if gpt_baseline:
        gpt_results = gpt_baseline
    elif 'gpt-5.1-chat-latest' in benchmarks:
        gpt_results = {r['id']: r for r in benchmarks['gpt-5.1-chat-latest']['results'] if 'error' not in r}
    else:
        return {}

    if not gpt_results:
        return {}

    # gpt_results가 이미 dict이면 그대로 사용
    if not isinstance(list(gpt_results.values())[0], dict):
        return {}

    comparison = {}

    for model, data in benchmarks.items():
        if model == 'gpt-5.1-chat-latest':
            continue

        model_results = {r['id']: r for r in data['results'] if 'error' not in r}

        matches = {
            'era': 0,
            'category': 0,
            'year_within_10': 0,
            'civilization': 0,
            'record_type': 0,
            'total': 0
        }

        for event_id, gpt_r in gpt_results.items():
            if event_id not in model_results:
                continue

            local_r = model_results[event_id]
            matches['total'] += 1

            if gpt_r.get('era') == local_r.get('era'):
                matches['era'] += 1
            if gpt_r.get('category') == local_r.get('category'):
                matches['category'] += 1
            if gpt_r.get('civilization') == local_r.get('civilization'):
                matches['civilization'] += 1
            if gpt_r.get('record_type') == local_r.get('record_type'):
                matches['record_type'] += 1

            # 연도 비교 (10년 이내)
            gpt_year = gpt_r.get('year_start')
            local_year = local_r.get('year_start')
            if gpt_year is not None and local_year is not None:
                if abs(gpt_year - local_year) <= 10:
                    matches['year_within_10'] += 1

        if matches['total'] > 0:
            comparison[model] = {
                'era_match': matches['era'] / matches['total'] * 100,
                'category_match': matches['category'] / matches['total'] * 100,
                'year_match': matches['year_within_10'] / matches['total'] * 100,
                'civilization_match': matches['civilization'] / matches['total'] * 100,
                'record_type_match': matches['record_type'] / matches['total'] * 100,
                'total_compared': matches['total']
            }

    return comparison


def print_summary_table(benchmarks: Dict[str, Dict], quality: Dict[str, Any]):
    """최종 결과 테이블 출력"""
    print("\n" + "="*80)
    print("벤치마크 결과 요약")
    print("="*80)

    # 속도 비교
    print("\n[ 속도 비교 ]")
    print(f"{'모델':<35} {'성공률':>8} {'평균시간':>10} {'tok/s':>10}")
    print("-"*70)

    for model, data in benchmarks.items():
        print(f"{model:<35} {data['success_rate']:>7.0f}% {data['avg_time_per_event']:>9.1f}s {data['avg_tokens_per_sec']:>9.1f}")

    # 품질 비교 (GPT 대비)
    if quality:
        print("\n[ 품질 비교 (GPT-5.1 대비 일치율) ]")
        print(f"{'모델':<35} {'Era':>8} {'Category':>10} {'Year±10':>10} {'Civ':>8} {'Type':>8}")
        print("-"*80)

        for model, scores in quality.items():
            print(f"{model:<35} {scores['era_match']:>7.0f}% {scores['category_match']:>9.0f}% "
                  f"{scores['year_match']:>9.0f}% {scores['civilization_match']:>7.0f}% {scores['record_type_match']:>7.0f}%")


def main():
    parser = argparse.ArgumentParser(description='로컬 모델 엔리치먼트 벤치마크')
    parser.add_argument('--model', type=str, help='특정 모델만 테스트')
    parser.add_argument('--include-gpt', action='store_true', help='GPT-5.1 새로 테스트')
    parser.add_argument('--use-gpt-baseline', action='store_true', default=True,
                        help='기존 GPT-5.1 결과와 비교 (기본값)')
    args = parser.parse_args()

    print("="*60)
    print("로컬 모델 엔리치먼트 벤치마크")
    print("="*60)

    # Ollama 상태 확인
    if not check_ollama_running():
        print("\n[ERROR] Ollama가 실행 중이 아닙니다.")
        print("'ollama serve' 명령으로 Ollama를 실행하세요.")
        return

    available = get_available_models()
    print(f"\n사용 가능한 모델: {', '.join(available)}")

    # 테스트할 모델 선정
    if args.model:
        models_to_test = [args.model]
    else:
        models_to_test = [m for m in LOCAL_MODELS if m in available]

    if not models_to_test:
        print("\n[ERROR] 테스트할 모델이 없습니다.")
        return

    print(f"테스트할 모델: {', '.join(models_to_test)}")

    # GPT 베이스라인 로드
    gpt_baseline = None
    if args.use_gpt_baseline:
        gpt_baseline = load_gpt_baseline()
        if gpt_baseline:
            print(f"\nGPT-5.1 베이스라인 로드: {len(gpt_baseline)}개 이벤트")
            print(f"  파일: {GPT_BASELINE_FILE.name}")

    # DB에서 동일한 이벤트 로드
    print(f"\nDB에서 이벤트 로드 중... (IDs: {GPT_TEST_EVENT_IDS})")
    events = load_events_from_db(GPT_TEST_EVENT_IDS)
    print(f"로드된 이벤트: {len(events)}개")

    for e in events:
        print(f"  - [{e['id']}] {e['title'][:50]}")

    # 벤치마크 실행
    benchmarks = {}

    # GPT-5.1 새로 테스트 (옵션)
    if args.include_gpt:
        if not os.getenv('OPENAI_API_KEY'):
            print("\n[WARN] OPENAI_API_KEY가 없어서 GPT-5.1 테스트를 건너뜁니다.")
        else:
            benchmarks['gpt-5.1-chat-latest'] = benchmark_model('gpt-5.1-chat-latest', events, is_gpt=True)

    # 로컬 모델들
    for model in models_to_test:
        benchmarks[model] = benchmark_model(model, events)

    # 품질 비교 (GPT 베이스라인 또는 새 테스트 결과)
    quality = compare_quality(benchmarks, gpt_baseline)

    # 결과 출력
    print_summary_table(benchmarks, quality)

    # GPT 베이스라인 정보도 출력
    if gpt_baseline and quality:
        print("\n[ GPT-5.1 베이스라인 (기존 결과) ]")
        print(f"{'이벤트 ID':<12} {'Era':<15} {'Category':<15} {'Year':<10}")
        print("-"*55)
        for eid, r in gpt_baseline.items():
            print(f"{eid:<12} {r.get('era', 'N/A'):<15} {r.get('category', 'N/A'):<15} {r.get('year_start', 'N/A'):<10}")

    # 결과 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"benchmark_{timestamp}.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'events_tested': len(events),
            'gpt_baseline_file': str(GPT_BASELINE_FILE) if gpt_baseline else None,
            'benchmarks': benchmarks,
            'quality_comparison': quality
        }, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_path}")


if __name__ == '__main__':
    main()
