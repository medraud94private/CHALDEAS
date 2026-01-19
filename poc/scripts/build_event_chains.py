#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Event Chain Builder - Phase 7 Historical Chain

이벤트 간 연결을 추출하여 event_connections 테이블에 저장합니다.

레이어 유형:
1. Person Chain: 같은 인물 관련 이벤트들
2. Location Chain: 같은 장소의 이벤트들
3. Causal Chain: 같은 소스가 언급하는 이벤트들

사용법:
    python build_event_chains.py --layer person
    python build_event_chains.py --layer location
    python build_event_chains.py --layer causal
    python build_event_chains.py --all
"""

import sys
import math
import argparse
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from psycopg2.extras import execute_values

# 기본 강도
BASE_STRENGTH = {
    'person': 10.0,
    'location': 5.0,
    'causal': 1.0,
    'thematic': 0.5,
}


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def calculate_source_factor(source_count):
    """소스 수에 따른 비선형 강화: n * (1 + ln(n))^1.5"""
    if source_count <= 0:
        return 0
    n = source_count
    return n * math.pow(1 + math.log(n), 1.5)


def determine_direction(year_a, year_b, connection_type='related'):
    """시간 기반 방향성 결정"""
    if year_a is None or year_b is None:
        return 'undirected'

    if connection_type == 'part_of':
        return 'undirected'

    time_diff = year_b - year_a

    if abs(time_diff) <= 10:
        return 'bidirectional'
    elif time_diff > 10:
        return 'forward'
    else:
        return 'backward'


def calculate_strength(layer_type, source_count=1, time_distance=None, layer_count=1):
    """연결 강도 계산"""
    base = BASE_STRENGTH.get(layer_type, 1.0)
    source_factor = calculate_source_factor(source_count)

    # 시간 근접성 (50년 이내)
    temporal_factor = 0
    if time_distance is not None:
        temporal_factor = max(0, (50 - time_distance) * 0.02)

    # 교차점 보너스
    intersection_bonus = (layer_count - 1) * 2.0

    return base + source_factor + temporal_factor + intersection_bonus


def build_person_chains(conn, dry_run=True):
    """Person Chain: 같은 인물 관련 이벤트들 연결"""
    cur = conn.cursor()

    print("\n=== Person Chain 추출 ===")

    # 인물별 이벤트 조회 (text_mentions에서 person 타입)
    cur.execute('''
        SELECT
            tm.entity_id as person_id,
            p.name as person_name,
            COUNT(DISTINCT e.id) as event_count
        FROM text_mentions tm
        JOIN persons p ON tm.entity_id = p.id
        JOIN events e ON tm.source_id IN (
            SELECT source_id FROM text_mentions
            WHERE entity_type = 'event' AND entity_id = e.id
        )
        WHERE tm.entity_type = 'person'
        GROUP BY tm.entity_id, p.name
        HAVING COUNT(DISTINCT e.id) >= 2
        ORDER BY event_count DESC
        LIMIT 100
    ''')

    # 더 간단한 접근: event에서 직접 person 언급 찾기 (1개 이상 전부)
    cur.execute('''
        SELECT
            p.id as person_id,
            p.name,
            COUNT(*) as event_count
        FROM persons p
        JOIN text_mentions tm ON tm.entity_id = p.id AND tm.entity_type = 'person'
        GROUP BY p.id, p.name
        HAVING COUNT(*) >= 1
        ORDER BY event_count DESC
    ''')

    persons = cur.fetchall()
    print(f"1개+ 멘션 인물: {len(persons)}명 (전체 처리)")

    # 모든 인물의 이벤트 쌍 생성 (컷오프 제거)
    total_connections = 0
    connections_to_insert = []
    total_persons = len(persons)

    for idx, (person_id, person_name, event_count) in enumerate(persons):  # 전체 처리
        if idx % 1000 == 0:
            print(f"  진행: {idx:,}/{total_persons:,} ({idx*100/total_persons:.1f}%)", flush=True)
        # 해당 인물 관련 이벤트들 조회
        cur.execute('''
            SELECT DISTINCT e.id, e.date_start
            FROM events e
            JOIN text_mentions tm ON tm.source_id IN (
                SELECT tm2.source_id FROM text_mentions tm2
                WHERE tm2.entity_type = 'event' AND tm2.entity_id = e.id
            )
            WHERE tm.entity_type = 'person' AND tm.entity_id = %s
            AND e.date_start IS NOT NULL
            ORDER BY e.date_start
        ''', (person_id,))

        events = cur.fetchall()

        # 연속된 이벤트 쌍 생성 (시간순)
        for i in range(len(events) - 1):
            event_a_id, year_a = events[i]
            event_b_id, year_b = events[i + 1]

            time_distance = abs(year_b - year_a) if year_a and year_b else None
            direction = determine_direction(year_a, year_b)
            strength = calculate_strength('person', source_count=1, time_distance=time_distance)

            connections_to_insert.append((
                event_a_id,
                event_b_id,
                direction,
                'person',
                person_id,
                'follows',  # 인물 체인은 기본적으로 follows
                strength,
                1,  # source_count
                time_distance,
                'unverified',
            ))
            total_connections += 1

    print(f"생성할 연결 수: {total_connections}")

    # 중복 제거 (같은 이벤트 쌍이 여러 인물에서 나올 수 있음)
    seen = set()
    unique_connections = []
    for c in connections_to_insert:
        key = (c[0], c[1], c[3])  # event_a_id, event_b_id, layer_type
        if key not in seen:
            seen.add(key)
            unique_connections.append(c)

    print(f"중복 제거 후: {len(unique_connections)}개")
    connections_to_insert = unique_connections

    if not dry_run and connections_to_insert:
        # 기존 연결 유지 (ON CONFLICT로 중복 처리)

        # 배치 삽입
        execute_values(cur, '''
            INSERT INTO event_connections
            (event_a_id, event_b_id, direction, layer_type, layer_entity_id,
             connection_type, strength_score, source_count, time_distance, verification_status)
            VALUES %s
            ON CONFLICT (event_a_id, event_b_id, layer_type) DO UPDATE
            SET strength_score = EXCLUDED.strength_score,
                direction = EXCLUDED.direction,
                updated_at = NOW()
        ''', connections_to_insert)

        conn.commit()
        print(f"[완료] {total_connections}개 연결 저장")

    return total_connections


def build_location_chains(conn, dry_run=True):
    """Location Chain: 같은 장소의 이벤트들 연결"""
    cur = conn.cursor()

    print("\n=== Location Chain 추출 ===")

    # 장소별 이벤트 수 조회
    cur.execute('''
        SELECT
            l.id as location_id,
            l.name,
            COUNT(*) as event_count
        FROM locations l
        JOIN events e ON e.primary_location_id = l.id
        WHERE e.date_start IS NOT NULL
        GROUP BY l.id, l.name
        HAVING COUNT(*) >= 2
        ORDER BY event_count DESC
    ''')

    locations = cur.fetchall()
    print(f"2개+ 이벤트 있는 장소: {len(locations)}곳")

    total_connections = 0
    connections_to_insert = []

    for location_id, location_name, event_count in locations[:1000]:  # 상위 1000곳
        # 해당 장소의 이벤트들 (시간순)
        cur.execute('''
            SELECT id, date_start
            FROM events
            WHERE primary_location_id = %s AND date_start IS NOT NULL
            ORDER BY date_start
        ''', (location_id,))

        events = cur.fetchall()

        # 연속된 이벤트 쌍 생성
        for i in range(len(events) - 1):
            event_a_id, year_a = events[i]
            event_b_id, year_b = events[i + 1]

            time_distance = abs(year_b - year_a) if year_a and year_b else None
            direction = determine_direction(year_a, year_b)
            strength = calculate_strength('location', source_count=1, time_distance=time_distance)

            connections_to_insert.append((
                event_a_id,
                event_b_id,
                direction,
                'location',
                location_id,
                'follows',
                strength,
                1,
                time_distance,
                'unverified',
            ))
            total_connections += 1

    print(f"생성할 연결 수: {total_connections}")

    if not dry_run and connections_to_insert:
        # 기존 연결 유지 (ON CONFLICT로 중복 처리)
        execute_values(cur, '''
            INSERT INTO event_connections
            (event_a_id, event_b_id, direction, layer_type, layer_entity_id,
             connection_type, strength_score, source_count, time_distance, verification_status)
            VALUES %s
            ON CONFLICT (event_a_id, event_b_id, layer_type) DO UPDATE
            SET strength_score = EXCLUDED.strength_score,
                direction = EXCLUDED.direction,
                updated_at = NOW()
        ''', connections_to_insert)

        conn.commit()
        print(f"[완료] {total_connections}개 연결 저장")

    return total_connections


def build_causal_chains(conn, dry_run=True):
    """Causal Chain: 같은 소스가 언급하는 이벤트들 연결"""
    cur = conn.cursor()

    print("\n=== Causal Chain 추출 (소스 기반) ===")

    # 같은 소스가 언급하는 이벤트 쌍 추출
    cur.execute('''
        SELECT
            tm1.entity_id as event_a_id,
            tm2.entity_id as event_b_id,
            COUNT(DISTINCT tm1.source_id) as source_count
        FROM text_mentions tm1
        JOIN text_mentions tm2
            ON tm1.source_id = tm2.source_id
            AND tm1.entity_type = 'event'
            AND tm2.entity_type = 'event'
            AND tm1.entity_id < tm2.entity_id
        GROUP BY tm1.entity_id, tm2.entity_id
        ORDER BY source_count DESC
    ''')

    pairs = cur.fetchall()
    print(f"소스 기반 이벤트 쌍: {len(pairs)}개")

    total_connections = 0
    connections_to_insert = []

    for event_a_id, event_b_id, source_count in pairs:
        # 이벤트 연도 조회
        cur.execute('''
            SELECT
                (SELECT date_start FROM events WHERE id = %s) as year_a,
                (SELECT date_start FROM events WHERE id = %s) as year_b
        ''', (event_a_id, event_b_id))

        result = cur.fetchone()
        year_a, year_b = result if result else (None, None)

        time_distance = abs(year_b - year_a) if year_a and year_b else None
        direction = determine_direction(year_a, year_b)
        strength = calculate_strength('causal', source_count=source_count, time_distance=time_distance)

        connections_to_insert.append((
            event_a_id,
            event_b_id,
            direction,
            'causal',
            None,  # layer_entity_id is NULL for causal
            None,  # connection_type to be determined by LLM
            strength,
            source_count,
            time_distance,
            'unverified',
        ))
        total_connections += 1

    print(f"생성할 연결 수: {total_connections}")

    # 강도 분포
    if connections_to_insert:
        strengths = [c[6] for c in connections_to_insert]
        print(f"\n강도 분포:")
        print(f"  - 최소: {min(strengths):.1f}")
        print(f"  - 최대: {max(strengths):.1f}")
        print(f"  - 평균: {sum(strengths)/len(strengths):.1f}")
        print(f"  - 강함 (>=10): {len([s for s in strengths if s >= 10])}개")
        print(f"  - 매우 강함 (>=30): {len([s for s in strengths if s >= 30])}개")

    if not dry_run and connections_to_insert:
        # 기존 연결 유지 (ON CONFLICT로 중복 처리)
        execute_values(cur, '''
            INSERT INTO event_connections
            (event_a_id, event_b_id, direction, layer_type, layer_entity_id,
             connection_type, strength_score, source_count, time_distance, verification_status)
            VALUES %s
            ON CONFLICT (event_a_id, event_b_id, layer_type) DO UPDATE
            SET strength_score = EXCLUDED.strength_score,
                source_count = EXCLUDED.source_count,
                direction = EXCLUDED.direction,
                updated_at = NOW()
        ''', connections_to_insert)

        conn.commit()
        print(f"\n[완료] {total_connections}개 연결 저장")

    return total_connections


def main():
    parser = argparse.ArgumentParser(description='Event Chain Builder')
    parser.add_argument('--layer', type=str, choices=['person', 'location', 'causal'],
                        help='추출할 레이어 유형')
    parser.add_argument('--all', action='store_true', help='모든 레이어 추출')
    parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 미리보기')

    args = parser.parse_args()

    if not args.layer and not args.all:
        parser.print_help()
        return

    conn = get_db_connection()

    print("=" * 60)
    print("EVENT CHAIN BUILDER - Phase 7")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")

    try:
        if args.all or args.layer == 'person':
            build_person_chains(conn, dry_run=args.dry_run)

        if args.all or args.layer == 'location':
            build_location_chains(conn, dry_run=args.dry_run)

        if args.all or args.layer == 'causal':
            build_causal_chains(conn, dry_run=args.dry_run)

        # 최종 통계
        if not args.dry_run:
            cur = conn.cursor()
            cur.execute('''
                SELECT layer_type, COUNT(*), AVG(strength_score)
                FROM event_connections
                GROUP BY layer_type
            ''')
            print("\n=== 최종 통계 ===")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]:,}개 (평균 강도: {row[2]:.1f})")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
