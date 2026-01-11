#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
이벤트 통합 스크립트 (DATA_RECONCILIATION_PLAN.md CP-R1~R5)

DB 고아 이벤트(9,518개)와 NER 추출 이벤트(124,080개) 매칭

사용법:
    # 매칭 테스트 (100개)
    python reconcile_events.py --test 100

    # 전체 매칭 실행
    python reconcile_events.py --full

    # 결과 분석
    python reconcile_events.py --analyze results/reconcile_YYYYMMDD.json

    # Source 연결 적용
    python reconcile_events.py --apply results/reconcile_YYYYMMDD.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from dotenv import load_dotenv
load_dotenv()

# Configuration
NER_DIR = Path(__file__).parent.parent / "data" / "integrated_ner_full"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "reconcile_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


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


def load_db_orphan_events() -> List[Dict]:
    """
    DB에서 source 연결이 없는 고아 이벤트 로드.
    text_mentions에 연결이 없는 events.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # source 연결이 없는 이벤트 (고아)
    cur.execute('''
        SELECT e.id, e.title, e.description, e.date_start, e.date_end,
               e.primary_location_id, l.name as location_name
        FROM events e
        LEFT JOIN locations l ON e.primary_location_id = l.id
        WHERE e.id NOT IN (
            SELECT DISTINCT entity_id
            FROM text_mentions
            WHERE entity_type = 'event'
        )
        ORDER BY e.id
    ''')

    events = []
    for row in cur.fetchall():
        events.append({
            'id': row[0],
            'title': row[1] or '',
            'description': (row[2] or '')[:500],
            'year_start': row[3],
            'year_end': row[4],
            'location_id': row[5],
            'location_name': row[6]
        })

    conn.close()
    print(f"DB 고아 이벤트 로드: {len(events):,}개")
    return events


def load_db_events_with_source() -> List[Dict]:
    """DB에서 source 연결이 있는 이벤트 로드 (매칭 제외용)."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT DISTINCT entity_id
        FROM text_mentions
        WHERE entity_type = 'event'
    ''')

    event_ids = set(row[0] for row in cur.fetchall())
    conn.close()
    print(f"Source 연결된 이벤트: {len(event_ids):,}개")
    return event_ids


def load_ner_events(limit: Optional[int] = None) -> List[Dict]:
    """
    NER 추출 이벤트 로드.
    minimal_batch_*_output.jsonl 파일들에서 events 추출.
    """
    output_files = sorted(NER_DIR.glob("minimal_batch_*_output.jsonl"))
    print(f"NER 파일 발견: {len(output_files)}개")

    events = []
    source_map = {}  # source_id -> source 정보

    for file_path in output_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    custom_id = record.get('custom_id', '')

                    # source 정보 추출
                    source_type, source_ref = parse_source_id(custom_id)

                    # response에서 content 추출
                    response = record.get('response', {})
                    if response.get('status_code') != 200:
                        continue

                    body = response.get('body', {})
                    choices = body.get('choices', [])
                    if not choices:
                        continue

                    content = choices[0].get('message', {}).get('content', '')
                    if not content:
                        continue

                    # JSON 파싱
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        continue

                    # events 추출
                    for evt in data.get('events', []):
                        events.append({
                            'source_id': custom_id,
                            'source_type': source_type,
                            'source_ref': source_ref,
                            'name': evt.get('name', ''),
                            'year': evt.get('year'),
                            'persons_involved': evt.get('persons_involved', []),
                            'locations_involved': evt.get('locations_involved', []),
                            'confidence': evt.get('confidence', 0.5)
                        })

                        if limit and len(events) >= limit:
                            print(f"NER 이벤트 로드: {len(events):,}개 (limit)")
                            return events

                except Exception as e:
                    continue

    print(f"NER 이벤트 로드: {len(events):,}개")
    return events


def parse_source_id(custom_id: str) -> Tuple[str, str]:
    """custom_id에서 source 타입과 참조 추출."""
    if custom_id.startswith('gutenberg_'):
        return 'gutenberg', custom_id.replace('gutenberg_', '')
    elif custom_id.startswith('wikipedia_'):
        return 'wikipedia', custom_id.replace('wikipedia_', '')
    elif custom_id.startswith('archive_'):
        return 'archive', custom_id.replace('archive_', '')
    else:
        return 'unknown', custom_id


def normalize_text(text: str) -> str:
    """텍스트 정규화 (소문자, 특수문자 제거)."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def fuzzy_match_score(text1: str, text2: str) -> float:
    """두 텍스트의 유사도 계산 (0-100)."""
    from difflib import SequenceMatcher

    # 정규화
    t1 = normalize_text(text1)
    t2 = normalize_text(text2)

    if not t1 or not t2:
        return 0.0

    # SequenceMatcher 사용
    ratio = SequenceMatcher(None, t1, t2).ratio()
    return ratio * 100


def year_proximity_score(year1: Optional[int], year2: Optional[int]) -> float:
    """연도 근접성 점수 (0-100). 10년 차이마다 -10점."""
    if year1 is None or year2 is None:
        return 50  # 연도 정보 없으면 중간값

    diff = abs(year1 - year2)
    score = max(0, 100 - diff * 10)
    return score


def person_overlap_score(db_event: Dict, ner_event: Dict) -> float:
    """관련 인물 겹침 점수 (0-100)."""
    ner_persons = ner_event.get('persons_involved', [])
    if not ner_persons or len(ner_persons) == 0:
        return 0  # 인물 정보 없으면 0 (중립 아님)

    ner_persons_normalized = set(normalize_text(p) for p in ner_persons if p)
    if not ner_persons_normalized:
        return 0

    # DB 이벤트의 description에서 인물명 매칭
    db_desc = normalize_text(db_event.get('description', ''))
    db_title = normalize_text(db_event.get('title', ''))
    db_text = db_desc + ' ' + db_title

    matches = sum(1 for p in ner_persons_normalized if p in db_text)
    if matches == 0:
        return 0
    return min(100, matches / len(ner_persons_normalized) * 100)


def location_overlap_score(db_event: Dict, ner_event: Dict) -> float:
    """관련 장소 겹침 점수 (0-100)."""
    ner_locations = ner_event.get('locations_involved', [])
    if not ner_locations or len(ner_locations) == 0:
        return 0  # 장소 정보 없으면 0 (중립 아님)

    ner_locations_normalized = set(normalize_text(loc) for loc in ner_locations if loc)
    if not ner_locations_normalized:
        return 0

    # DB 이벤트의 location_name, description에서 매칭
    db_loc = normalize_text(db_event.get('location_name', '') or '')
    db_desc = normalize_text(db_event.get('description', ''))
    db_text = db_loc + ' ' + db_desc

    matches = sum(1 for loc in ner_locations_normalized if loc in db_text)
    if matches == 0:
        return 0
    return min(100, matches / len(ner_locations_normalized) * 100)


def match_events(db_event: Dict, ner_event: Dict) -> Tuple[float, Dict]:
    """
    DB 이벤트와 NER 이벤트 매칭 점수 계산.

    가중치 (정보 유무에 따라 동적 조정):
    - 제목 유사도: 기본 50%
    - 연도 근접성: 기본 30%
    - 인물 겹침: 기본 10%
    - 장소 겹침: 기본 10%
    """
    # 1. 제목 유사도 (항상 중요)
    title_score = fuzzy_match_score(db_event['title'], ner_event['name'])

    # 2. 연도 근접성
    db_year = db_event.get('year_start')
    ner_year = ner_event.get('year')
    has_both_years = db_year is not None and ner_year is not None

    if has_both_years:
        year_score = year_proximity_score(db_year, ner_year)
    else:
        year_score = 0  # 연도 정보 없으면 0

    # 3. 인물 겹침
    person_score = person_overlap_score(db_event, ner_event)

    # 4. 장소 겹침
    location_score = location_overlap_score(db_event, ner_event)

    # 동적 가중치 계산
    # 제목은 항상 높은 가중치
    title_weight = 0.60

    # 연도가 있으면 연도 가중치 추가
    if has_both_years:
        year_weight = 0.30
        title_weight = 0.50  # 제목 가중치 약간 감소
    else:
        year_weight = 0

    # 인물/장소 정보가 있으면 가중치 부여
    person_weight = 0.05 if person_score > 0 else 0
    location_weight = 0.05 if location_score > 0 else 0

    # 남은 가중치를 제목에 추가
    remaining = 1.0 - (title_weight + year_weight + person_weight + location_weight)
    title_weight += remaining

    # 가중 합계
    total_score = (
        title_score * title_weight +
        year_score * year_weight +
        person_score * person_weight +
        location_score * location_weight
    )

    # 연도가 정확히 일치하면 보너스
    if has_both_years and db_year == ner_year:
        total_score = min(100, total_score + 10)

    details = {
        'title_score': round(title_score, 1),
        'year_score': round(year_score, 1),
        'person_score': round(person_score, 1),
        'location_score': round(location_score, 1),
        'weights': f"t:{title_weight:.2f},y:{year_weight:.2f},p:{person_weight:.2f},l:{location_weight:.2f}",
        'total_score': round(total_score, 1)
    }

    return total_score, details


def classify_match(score: float) -> str:
    """점수에 따른 매칭 결과 분류."""
    if score >= 85:
        return "AUTO_MATCH"
    elif score >= 60:
        return "REVIEW"
    else:
        return "NO_MATCH"


def run_matching(db_events: List[Dict], ner_events: List[Dict],
                 top_k: int = 3) -> Dict[int, List[Dict]]:
    """
    모든 DB 이벤트에 대해 NER 이벤트 매칭 실행.
    각 DB 이벤트마다 상위 top_k개 매칭 후보 반환.
    """
    from tqdm import tqdm

    results = {}

    print(f"\n매칭 시작: {len(db_events):,} DB 이벤트 × {len(ner_events):,} NER 이벤트")

    for db_evt in tqdm(db_events, desc="매칭 중"):
        candidates = []

        for ner_evt in ner_events:
            score, details = match_events(db_evt, ner_evt)

            if score >= 30:  # 최소 임계값
                candidates.append({
                    'ner_source_id': ner_evt['source_id'],
                    'ner_name': ner_evt['name'],
                    'ner_year': ner_evt.get('year'),
                    'score': score,
                    'classification': classify_match(score),
                    'details': details
                })

        # 상위 top_k 선택
        candidates.sort(key=lambda x: x['score'], reverse=True)
        results[db_evt['id']] = candidates[:top_k]

    return results


def run_matching_optimized(db_events: List[Dict], ner_events: List[Dict],
                           top_k: int = 3) -> Dict[int, List[Dict]]:
    """
    최적화된 매칭: 인덱싱 + 프루닝 사용.
    """
    from tqdm import tqdm
    import re

    # NER 이벤트 인덱싱 (단어 기반)
    print("NER 이벤트 인덱싱 중...")
    word_index = defaultdict(list)
    for i, ner_evt in enumerate(ner_events):
        words = set(normalize_text(ner_evt['name']).split())
        for word in words:
            if len(word) >= 3:  # 3글자 이상 단어만
                word_index[word].append(i)

    print(f"인덱스 크기: {len(word_index):,} 단어")

    results = {}

    for db_evt in tqdm(db_events, desc="매칭 중"):
        # DB 이벤트 제목에서 단어 추출
        db_words = set(normalize_text(db_evt['title']).split())

        # 관련 NER 이벤트 후보 수집 (인덱스 기반)
        candidate_indices = set()
        for word in db_words:
            if len(word) >= 3 and word in word_index:
                candidate_indices.update(word_index[word][:500])  # 단어당 최대 500개

        # 후보가 너무 적으면 전체 스캔
        if len(candidate_indices) < 10:
            candidate_indices = set(range(min(1000, len(ner_events))))

        # 후보에 대해서만 상세 매칭
        candidates = []
        for idx in candidate_indices:
            ner_evt = ner_events[idx]
            score, details = match_events(db_evt, ner_evt)

            if score >= 40:  # 임계값
                candidates.append({
                    'ner_source_id': ner_evt['source_id'],
                    'ner_name': ner_evt['name'],
                    'ner_year': ner_evt.get('year'),
                    'ner_source_type': ner_evt.get('source_type'),
                    'score': score,
                    'classification': classify_match(score),
                    'details': details
                })

        # 상위 top_k 선택
        candidates.sort(key=lambda x: x['score'], reverse=True)
        results[db_evt['id']] = candidates[:top_k]

    return results


def analyze_results(results: Dict[int, List[Dict]], db_events: List[Dict]) -> Dict:
    """매칭 결과 분석."""
    stats = {
        'total_db_events': len(db_events),
        'auto_match': 0,
        'review': 0,
        'no_match': 0,
        'avg_top_score': 0,
        'score_distribution': defaultdict(int)
    }

    total_top_score = 0

    for db_id, candidates in results.items():
        if not candidates:
            stats['no_match'] += 1
            continue

        top = candidates[0]
        classification = top['classification']
        score = top['score']

        if classification == 'AUTO_MATCH':
            stats['auto_match'] += 1
        elif classification == 'REVIEW':
            stats['review'] += 1
        else:
            stats['no_match'] += 1

        total_top_score += score

        # 점수 분포 (10점 단위)
        bucket = int(score // 10) * 10
        stats['score_distribution'][bucket] += 1

    if results:
        stats['avg_top_score'] = round(total_top_score / len(results), 1)

    # 분포를 리스트로 변환
    stats['score_distribution'] = dict(sorted(stats['score_distribution'].items()))

    return stats


def print_sample_matches(results: Dict[int, List[Dict]], db_events: List[Dict], n: int = 10):
    """샘플 매칭 결과 출력."""
    db_map = {e['id']: e for e in db_events}

    print(f"\n{'='*80}")
    print(f"샘플 매칭 결과 (상위 {n}개)")
    print(f"{'='*80}")

    # 고득점 매칭
    scored = [(db_id, cands[0]) for db_id, cands in results.items() if cands]
    scored.sort(key=lambda x: x[1]['score'], reverse=True)

    for db_id, top_match in scored[:n]:
        db_evt = db_map.get(db_id, {})
        print(f"\n[{top_match['classification']}] Score: {top_match['score']:.1f}")
        print(f"  DB: [{db_id}] {db_evt.get('title', 'N/A')[:60]}")
        print(f"  NER: {top_match['ner_name'][:60]}")
        print(f"  Source: {top_match['ner_source_id']}")
        print(f"  Details: {top_match['details']}")


def save_results(results: Dict[int, List[Dict]], db_events: List[Dict],
                 ner_count: int, output_path: Path):
    """결과 저장."""
    stats = analyze_results(results, db_events)

    data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'db_events_count': len(db_events),
            'ner_events_count': ner_count
        },
        'statistics': stats,
        'matches': {str(k): v for k, v in results.items()}  # JSON key는 문자열
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_path}")


def run_test(count: int = 100):
    """테스트 실행."""
    print(f"\n=== 테스트 모드: {count}개 DB 이벤트 ===\n")

    # DB 이벤트 로드 (제한)
    db_events = load_db_orphan_events()[:count]

    # NER 이벤트 로드 (제한)
    ner_events = load_ner_events(limit=10000)

    # 매칭 실행
    results = run_matching_optimized(db_events, ner_events)

    # 결과 분석
    stats = analyze_results(results, db_events)

    print(f"\n{'='*60}")
    print("매칭 결과 통계")
    print(f"{'='*60}")
    print(f"총 DB 이벤트: {stats['total_db_events']:,}")
    print(f"AUTO_MATCH (≥85): {stats['auto_match']:,} ({stats['auto_match']/stats['total_db_events']*100:.1f}%)")
    print(f"REVIEW (60-85): {stats['review']:,} ({stats['review']/stats['total_db_events']*100:.1f}%)")
    print(f"NO_MATCH (<60): {stats['no_match']:,} ({stats['no_match']/stats['total_db_events']*100:.1f}%)")
    print(f"평균 최고 점수: {stats['avg_top_score']}")

    print(f"\n점수 분포:")
    for bucket, count in sorted(stats['score_distribution'].items()):
        bar = '█' * (count * 50 // stats['total_db_events'])
        print(f"  {bucket:3d}-{bucket+9:3d}: {count:4d} {bar}")

    # 샘플 출력
    print_sample_matches(results, db_events)

    # 결과 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"test_{timestamp}.json"
    save_results(results, db_events, len(ner_events), output_path)


def run_full():
    """전체 매칭 실행."""
    print(f"\n=== 전체 매칭 모드 ===\n")

    # DB 고아 이벤트 로드
    db_events = load_db_orphan_events()

    # NER 이벤트 전체 로드
    ner_events = load_ner_events()

    # 매칭 실행
    results = run_matching_optimized(db_events, ner_events)

    # 결과 분석
    stats = analyze_results(results, db_events)

    print(f"\n{'='*60}")
    print("전체 매칭 결과")
    print(f"{'='*60}")
    print(f"총 DB 이벤트: {stats['total_db_events']:,}")
    print(f"AUTO_MATCH: {stats['auto_match']:,}")
    print(f"REVIEW: {stats['review']:,}")
    print(f"NO_MATCH: {stats['no_match']:,}")

    # 결과 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"full_{timestamp}.json"
    save_results(results, db_events, len(ner_events), output_path)


def verify_with_local_llm(db_event: Dict, ner_event: Dict, model: str = "qwen3:1.7b") -> Dict:
    """
    로컬 LLM으로 매칭 검증.
    REVIEW 레벨 매칭에 대해 AI 판단 수행.
    """
    import requests

    OLLAMA_URL = "http://localhost:11434"

    prompt = f"""두 역사적 이벤트가 같은 사건인지 판단하세요.

이벤트 1 (DB):
- 제목: {db_event.get('title', 'N/A')}
- 연도: {db_event.get('year_start', 'N/A')}
- 설명: {db_event.get('description', 'N/A')[:200]}
- 장소: {db_event.get('location_name', 'N/A')}

이벤트 2 (NER):
- 이름: {ner_event.get('name', 'N/A')}
- 연도: {ner_event.get('year', 'N/A')}
- 관련 인물: {', '.join(ner_event.get('persons_involved', [])[:3])}
- 관련 장소: {', '.join(ner_event.get('locations_involved', [])[:3])}

JSON 형식으로만 응답:
{{"is_same": true/false, "confidence": 0.0-1.0, "reason": "간단한 이유"}}"""

    # Qwen3 thinking mode 비활성화
    if 'qwen3' in model.lower():
        prompt = prompt + "\n\n/nothink"

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 200}
            },
            timeout=30
        )

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "is_same": None}

        content = resp.json().get('message', {}).get('content', '')

        # JSON 추출
        import re
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {"error": "JSON not found", "raw": content[:100], "is_same": None}

    except Exception as e:
        return {"error": str(e), "is_same": None}


def run_ai_verification(results: Dict[int, List[Dict]], db_events: List[Dict],
                        ner_events: List[Dict], model: str = "qwen3:1.7b") -> Dict[int, List[Dict]]:
    """
    REVIEW 레벨 매칭에 대해 AI 검증 수행.
    """
    from tqdm import tqdm
    import requests

    # Ollama 확인
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code != 200:
            print("[WARN] Ollama 미실행. AI 검증 건너뜀.")
            return results
    except:
        print("[WARN] Ollama 연결 실패. AI 검증 건너뜀.")
        return results

    db_map = {e['id']: e for e in db_events}
    ner_map = {e['source_id'] + '::' + e['name']: e for e in ner_events}

    review_count = sum(1 for cands in results.values()
                       if cands and cands[0]['classification'] == 'REVIEW')
    print(f"\nAI 검증 대상: {review_count}개 REVIEW 매칭")

    verified = 0
    upgraded = 0
    downgraded = 0

    for db_id, candidates in tqdm(results.items(), desc="AI 검증 중"):
        if not candidates:
            continue

        top = candidates[0]
        if top['classification'] != 'REVIEW':
            continue

        db_evt = db_map.get(db_id, {})
        ner_key = top['ner_source_id'] + '::' + top['ner_name']
        ner_evt = ner_map.get(ner_key, {'name': top['ner_name'], 'year': top.get('ner_year')})

        result = verify_with_local_llm(db_evt, ner_evt, model)
        verified += 1

        if result.get('is_same') is True and result.get('confidence', 0) >= 0.7:
            # 업그레이드
            top['classification'] = 'AI_VERIFIED'
            top['ai_result'] = result
            upgraded += 1
        elif result.get('is_same') is False:
            # 다운그레이드
            top['classification'] = 'AI_REJECTED'
            top['ai_result'] = result
            downgraded += 1
        else:
            top['ai_result'] = result

    print(f"AI 검증 완료: {verified}건")
    print(f"  업그레이드 (AI_VERIFIED): {upgraded}")
    print(f"  다운그레이드 (AI_REJECTED): {downgraded}")

    return results


def apply_matches(results_file: str):
    """매칭 결과를 DB에 적용 (text_mentions 추가)."""
    print(f"\n=== 매칭 결과 적용: {results_file} ===\n")

    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    matches = data.get('matches', {})

    # AUTO_MATCH만 적용
    auto_matches = []
    for db_id_str, candidates in matches.items():
        if not candidates:
            continue
        top = candidates[0]
        if top['classification'] == 'AUTO_MATCH':
            auto_matches.append({
                'db_event_id': int(db_id_str),
                'ner_source_id': top['ner_source_id'],
                'ner_name': top['ner_name'],
                'score': top['score']
            })

    print(f"적용할 AUTO_MATCH: {len(auto_matches):,}개")

    if not auto_matches:
        print("적용할 매칭이 없습니다.")
        return

    # DB 적용
    conn = get_db_connection()
    cur = conn.cursor()

    # source_id 조회 (sources 테이블에서)
    applied = 0
    for match in auto_matches:
        # source 조회
        cur.execute('''
            SELECT id FROM sources
            WHERE source_type = %s AND source_ref = %s
            LIMIT 1
        ''', parse_source_id(match['ner_source_id']))

        row = cur.fetchone()
        if not row:
            continue

        source_id = row[0]

        # text_mentions에 추가
        try:
            cur.execute('''
                INSERT INTO text_mentions
                (entity_type, entity_id, source_id, mention_text, confidence, extraction_model)
                VALUES ('event', %s, %s, %s, %s, 'reconciliation')
                ON CONFLICT DO NOTHING
            ''', (match['db_event_id'], source_id, match['ner_name'], match['score'] / 100.0))
            applied += 1
        except Exception as e:
            print(f"에러: {e}")

    conn.commit()
    conn.close()

    print(f"적용 완료: {applied:,}개")


def run_test_with_ai(count: int = 100, model: str = "qwen3:1.7b"):
    """테스트 + AI 검증 실행."""
    print(f"\n=== 테스트 모드 + AI 검증: {count}개 DB 이벤트 (모델: {model}) ===\n")

    # DB 이벤트 로드
    db_events = load_db_orphan_events()[:count]
    ner_events = load_ner_events(limit=10000)

    # 1차 기계 매칭
    results = run_matching_optimized(db_events, ner_events)

    # 2차 AI 검증
    results = run_ai_verification(results, db_events, ner_events, model)

    # 결과 분석 (AI 결과 포함)
    stats = analyze_results(results, db_events)

    # AI 분류 추가 통계
    ai_verified = sum(1 for cands in results.values()
                      if cands and cands[0].get('classification') == 'AI_VERIFIED')
    ai_rejected = sum(1 for cands in results.values()
                      if cands and cands[0].get('classification') == 'AI_REJECTED')

    print(f"\n{'='*60}")
    print("최종 결과 (기계 + AI 검증)")
    print(f"{'='*60}")
    print(f"AUTO_MATCH: {stats['auto_match']:,}")
    print(f"AI_VERIFIED: {ai_verified:,}")
    print(f"AI_REJECTED: {ai_rejected:,}")
    print(f"REVIEW (미검증): {stats['review'] - ai_verified - ai_rejected:,}")
    print(f"NO_MATCH: {stats['no_match']:,}")

    # 샘플 출력
    print_sample_matches(results, db_events)

    # 결과 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"test_ai_{timestamp}.json"
    save_results(results, db_events, len(ner_events), output_path)


def main():
    parser = argparse.ArgumentParser(description='이벤트 통합 (DB ↔ NER 매칭)')
    parser.add_argument('--test', type=int, metavar='N', help='테스트 모드 (N개 DB 이벤트)')
    parser.add_argument('--test-ai', type=int, metavar='N', help='테스트 + AI 검증 (N개)')
    parser.add_argument('--model', type=str, default='qwen3:1.7b', help='AI 검증 모델 (기본: qwen3:1.7b)')
    parser.add_argument('--full', action='store_true', help='전체 매칭 실행')
    parser.add_argument('--full-ai', action='store_true', help='전체 매칭 + AI 검증')
    parser.add_argument('--analyze', type=str, metavar='FILE', help='결과 파일 분석')
    parser.add_argument('--apply', type=str, metavar='FILE', help='매칭 결과 DB 적용')

    args = parser.parse_args()

    if args.test:
        run_test(args.test)
    elif args.test_ai:
        run_test_with_ai(args.test_ai, args.model)
    elif args.full:
        run_full()
    elif args.full_ai:
        print("전체 + AI 검증 모드는 시간이 오래 걸립니다.")
        db_events = load_db_orphan_events()
        ner_events = load_ner_events()
        results = run_matching_optimized(db_events, ner_events)
        results = run_ai_verification(results, db_events, ner_events, args.model)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = RESULTS_DIR / f"full_ai_{timestamp}.json"
        save_results(results, db_events, len(ner_events), output_path)
    elif args.analyze:
        with open(args.analyze, 'r', encoding='utf-8') as f:
            data = json.load(f)
        stats = data.get('statistics', {})
        print(json.dumps(stats, indent=2))
    elif args.apply:
        apply_matches(args.apply)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
