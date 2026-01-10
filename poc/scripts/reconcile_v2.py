#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
이벤트 매칭/통합 V2

방식:
1. 정확 매칭: 제목+연도 100% 일치
2. 위치 매칭: 좌표+연도 일치 + 제목 유사(80%+)
3. AI 검증: 애매한 건 LLM으로 확인

사용법:
    python reconcile_v2.py --test 100      # 테스트
    python reconcile_v2.py --full          # 전체 실행
    python reconcile_v2.py --apply FILE    # 결과 적용
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from difflib import SequenceMatcher

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from openai import OpenAI

# Configuration
RESULTS_DIR = Path(__file__).parent.parent / "data" / "reconcile_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def normalize_title(title: str) -> str:
    """제목 정규화."""
    import re
    if not title:
        return ""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def title_similarity(t1: str, t2: str) -> float:
    """제목 유사도 (0-100)."""
    n1 = normalize_title(t1)
    n2 = normalize_title(t2)
    if not n1 or not n2:
        return 0
    return SequenceMatcher(None, n1, n2).ratio() * 100


def load_events() -> Tuple[List[Dict], List[Dict]]:
    """V0와 NER 이벤트 로드."""
    conn = get_db_connection()
    cur = conn.cursor()

    # V0 events
    cur.execute('''
        SELECT e.id, e.title, e.date_start, e.date_end,
               e.primary_location_id, l.latitude, l.longitude
        FROM events e
        LEFT JOIN locations l ON e.primary_location_id = l.id
        WHERE e.slug NOT LIKE 'ner-%%'
    ''')
    v0_events = []
    for row in cur.fetchall():
        v0_events.append({
            'id': row[0],
            'title': row[1] or '',
            'year_start': row[2],
            'year_end': row[3],
            'location_id': row[4],
            'lat': row[5],
            'lon': row[6]
        })

    # NER events
    cur.execute('''
        SELECT e.id, e.title, e.date_start, e.date_end,
               e.primary_location_id, l.latitude, l.longitude
        FROM events e
        LEFT JOIN locations l ON e.primary_location_id = l.id
        WHERE e.slug LIKE 'ner-%%'
    ''')
    ner_events = []
    for row in cur.fetchall():
        ner_events.append({
            'id': row[0],
            'title': row[1] or '',
            'year_start': row[2],
            'year_end': row[3],
            'location_id': row[4],
            'lat': row[5],
            'lon': row[6]
        })

    conn.close()
    return v0_events, ner_events


def find_exact_matches(v0_events: List[Dict], ner_events: List[Dict]) -> List[Dict]:
    """정확 매칭: 제목+연도 100% 일치."""
    matches = []

    # Build index for V0 events
    v0_index = defaultdict(list)
    for evt in v0_events:
        key = (normalize_title(evt['title']), evt['year_start'])
        v0_index[key].append(evt)

    # Find matches
    for ner in ner_events:
        key = (normalize_title(ner['title']), ner['year_start'])
        if key in v0_index:
            for v0 in v0_index[key]:
                matches.append({
                    'v0_id': v0['id'],
                    'v0_title': v0['title'],
                    'ner_id': ner['id'],
                    'ner_title': ner['title'],
                    'year': ner['year_start'],
                    'match_type': 'EXACT',
                    'confidence': 100,
                    'auto_merge': True
                })

    return matches


def find_location_matches(v0_events: List[Dict], ner_events: List[Dict],
                          matched_ner_ids: set) -> List[Dict]:
    """위치 매칭: 좌표+연도 일치 + 제목 유사."""
    matches = []

    # Build spatial index for V0 events with coordinates
    v0_with_loc = [e for e in v0_events if e['lat'] and e['lon'] and e['year_start']]

    for ner in ner_events:
        if ner['id'] in matched_ner_ids:
            continue
        if not ner['lat'] or not ner['lon'] or not ner['year_start']:
            continue

        for v0 in v0_with_loc:
            # Same year
            if v0['year_start'] != ner['year_start']:
                continue

            # Same location (within ~10km)
            lat_diff = abs(v0['lat'] - ner['lat'])
            lon_diff = abs(v0['lon'] - ner['lon'])
            if lat_diff > 0.1 or lon_diff > 0.1:
                continue

            # Title similarity
            sim = title_similarity(v0['title'], ner['title'])
            if sim >= 80:
                matches.append({
                    'v0_id': v0['id'],
                    'v0_title': v0['title'],
                    'ner_id': ner['id'],
                    'ner_title': ner['title'],
                    'year': ner['year_start'],
                    'match_type': 'LOCATION',
                    'confidence': sim,
                    'auto_merge': True
                })
            elif sim >= 50:
                matches.append({
                    'v0_id': v0['id'],
                    'v0_title': v0['title'],
                    'ner_id': ner['id'],
                    'ner_title': ner['title'],
                    'year': ner['year_start'],
                    'match_type': 'LOCATION_REVIEW',
                    'confidence': sim,
                    'auto_merge': False,
                    'needs_ai': True
                })

    return matches


def verify_with_ai(matches: List[Dict], client: OpenAI) -> List[Dict]:
    """AI로 애매한 매칭 검증."""
    needs_verification = [m for m in matches if m.get('needs_ai')]

    if not needs_verification:
        return matches

    print(f"\nAI 검증: {len(needs_verification)}건", flush=True)

    verified_count = 0
    for match in needs_verification:
        verified_count += 1
        if verified_count % 100 == 0:
            print(f"  AI 검증 진행: {verified_count}/{len(needs_verification)}", flush=True)
        prompt = f"""두 역사적 이벤트가 같은 사건인지 판단하세요.

이벤트 1: "{match['v0_title']}" (연도: {match['year']})
이벤트 2: "{match['ner_title']}" (연도: {match['year']})

같은 사건이면 {{"same": true, "confidence": 0.0-1.0}}
다른 사건이면 {{"same": false, "confidence": 0.0-1.0}}

JSON만 응답:"""

        try:
            response = client.chat.completions.create(
                model='gpt-5.1-chat-latest',
                messages=[{'role': 'user', 'content': prompt}],
                max_completion_tokens=100
            )

            content = response.choices[0].message.content.strip()

            import re
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                result = json.loads(json_match.group())
                if result.get('same') and result.get('confidence', 0) >= 0.7:
                    match['auto_merge'] = True
                    match['ai_verified'] = True
                    match['ai_confidence'] = result.get('confidence')
                else:
                    match['auto_merge'] = False
                    match['ai_rejected'] = True
        except Exception as e:
            match['ai_error'] = str(e)

    return matches


def run_reconciliation(test_limit: Optional[int] = None, use_ai: bool = True):
    """매칭 실행."""
    print("=" * 60, flush=True)
    print("이벤트 매칭/통합 V2", flush=True)
    print("=" * 60, flush=True)

    # Load events
    print("\n이벤트 로드 중...", flush=True)
    v0_events, ner_events = load_events()
    print(f"V0: {len(v0_events):,}개, NER: {len(ner_events):,}개", flush=True)

    if test_limit:
        ner_events = ner_events[:test_limit]
        print(f"테스트 모드: NER {len(ner_events)}개만 처리")

    # 1. Exact matches
    print("\n[1/3] 정확 매칭 (제목+연도 100% 일치)...", flush=True)
    exact_matches = find_exact_matches(v0_events, ner_events)
    print(f"  -> {len(exact_matches)}건 발견", flush=True)

    matched_ner_ids = {m['ner_id'] for m in exact_matches}

    # 2. Location matches
    print("\n[2/3] 위치 매칭 (좌표+연도+제목유사)...", flush=True)
    location_matches = find_location_matches(v0_events, ner_events, matched_ner_ids)
    auto_loc = [m for m in location_matches if m['auto_merge']]
    review_loc = [m for m in location_matches if not m['auto_merge']]
    print(f"  -> 자동: {len(auto_loc)}건, 검토 필요: {len(review_loc)}건", flush=True)

    # 3. AI verification
    all_matches = exact_matches + location_matches

    if use_ai and review_loc:
        print("\n[3/3] AI 검증...")
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        all_matches = verify_with_ai(all_matches, client)
        ai_verified = sum(1 for m in all_matches if m.get('ai_verified'))
        ai_rejected = sum(1 for m in all_matches if m.get('ai_rejected'))
        print(f"  -> 승인: {ai_verified}건, 거부: {ai_rejected}건")
    else:
        print("\n[3/3] AI 검증 스킵")

    # Summary
    auto_merge = [m for m in all_matches if m['auto_merge']]

    print("\n" + "=" * 60)
    print("결과 요약")
    print("=" * 60)
    print(f"총 매칭: {len(all_matches)}건")
    print(f"  - 정확 매칭: {len(exact_matches)}건")
    print(f"  - 위치 매칭 (자동): {len(auto_loc)}건")
    print(f"  - AI 검증 통과: {sum(1 for m in all_matches if m.get('ai_verified'))}건")
    print(f"자동 통합 가능: {len(auto_merge)}건")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = RESULTS_DIR / f"reconcile_v2_{timestamp}.json"

    output_data = {
        'metadata': {
            'timestamp': timestamp,
            'v0_count': len(v0_events),
            'ner_count': len(ner_events),
            'test_limit': test_limit
        },
        'summary': {
            'total_matches': len(all_matches),
            'exact_matches': len(exact_matches),
            'location_matches': len(location_matches),
            'auto_merge': len(auto_merge)
        },
        'matches': all_matches
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_path}")

    # Show examples
    print("\n[예시 - 정확 매칭]")
    for m in exact_matches[:3]:
        print(f"  V0: {m['v0_title'][:40]}")
        print(f"  NER: {m['ner_title'][:40]}")
        print(f"  연도: {m['year']}")
        print()

    return output_path


def apply_merges(results_file: str):
    """매칭 결과 적용 - NER 이벤트를 V0에 통합."""
    print(f"\n매칭 결과 적용: {results_file}")

    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    matches = data['matches']
    auto_merge = [m for m in matches if m['auto_merge']]

    print(f"자동 통합 대상: {len(auto_merge)}건")

    if not auto_merge:
        print("통합할 매칭이 없습니다.")
        return

    conn = get_db_connection()
    cur = conn.cursor()

    merged = 0
    skipped = 0
    for match in auto_merge:
        v0_id = match['v0_id']
        ner_id = match['ner_id']

        try:
            # NER 이벤트에 merged_into 표시 (slug 접두어로 표시)
            cur.execute('''
                UPDATE events
                SET slug = 'merged-' || slug,
                    description = COALESCE(description, '') || %s
                WHERE id = %s AND slug NOT LIKE 'merged-%%'
            ''', (f' [MERGED INTO {v0_id}]', ner_id))

            if cur.rowcount > 0:
                merged += 1
            else:
                skipped += 1

            # 100건마다 커밋
            if merged % 100 == 0:
                conn.commit()
                print(f"  진행: {merged}건 완료", flush=True)

        except Exception as e:
            print(f"Error merging {ner_id} -> {v0_id}: {e}")
            conn.rollback()

    conn.commit()
    conn.close()

    print(f"\n통합 완료: {merged}건 (스킵: {skipped}건)")


def main():
    parser = argparse.ArgumentParser(description='이벤트 매칭/통합 V2')
    parser.add_argument('--test', type=int, metavar='N', help='테스트 (N개 NER)')
    parser.add_argument('--full', action='store_true', help='전체 실행')
    parser.add_argument('--no-ai', action='store_true', help='AI 검증 스킵')
    parser.add_argument('--apply', type=str, metavar='FILE', help='결과 적용')

    args = parser.parse_args()

    if args.test:
        run_reconciliation(test_limit=args.test, use_ai=not args.no_ai)
    elif args.full:
        run_reconciliation(use_ai=not args.no_ai)
    elif args.apply:
        apply_merges(args.apply)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
