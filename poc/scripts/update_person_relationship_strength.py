#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person-Person 관계 강도 업데이트 스크립트

강도 계산:
1. Source Factor: 공유 소스 수 (n * (1 + ln(n))^1.5)
2. Location Factor: 공유 장소 수 * 2.0
3. Temporal Factor: 시대 중첩 보너스 (최대 10점)
   - 생몰년 겹침 = +10
   - 50년 이내 = +5
   - 100년 이내 = +2
   - 그 외 = 0 (또는 페널티)
"""

import sys
import math

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def calculate_source_factor(source_count):
    """소스 수에 따른 비선형 강화"""
    if source_count <= 0:
        return 0
    n = source_count
    return n * math.pow(1 + math.log(n), 1.5)


def calculate_temporal_overlap(p1_birth, p1_death, p2_birth, p2_death):
    """
    두 인물의 시간적 중첩 계산.
    Returns: (overlap_score, time_distance)
    """
    # 연도 정보 없으면 중립
    if all(x is None for x in [p1_birth, p1_death, p2_birth, p2_death]):
        return 0, None

    # floruit 추정 (birth/death 없으면)
    def get_active_period(birth, death):
        if birth and death:
            return birth, death
        elif birth:
            return birth, birth + 70  # 평균 수명 가정
        elif death:
            return death - 70, death
        else:
            return None, None

    p1_start, p1_end = get_active_period(p1_birth, p1_death)
    p2_start, p2_end = get_active_period(p2_birth, p2_death)

    if p1_start is None or p2_start is None:
        return 0, None

    # 중첩 계산
    overlap_start = max(p1_start, p2_start)
    overlap_end = min(p1_end, p2_end)

    if overlap_start <= overlap_end:
        # 실제 중첩 있음
        overlap_years = overlap_end - overlap_start
        if overlap_years >= 20:
            return 10, 0  # 동시대인
        elif overlap_years >= 10:
            return 7, 0
        else:
            return 5, 0
    else:
        # 중첩 없음 - 시간 거리 계산
        time_distance = overlap_start - overlap_end  # 양수 = 떨어진 년수

        if time_distance <= 50:
            return 2, time_distance
        elif time_distance <= 100:
            return 0, time_distance
        else:
            return -5, time_distance  # 페널티 (너무 동떨어진 시대)


def update_strengths(dry_run=True):
    print("=" * 60)
    print("Person Relationship Strength Update")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # 모든 관계 조회 (인물 정보 포함)
    print("\nLoading relationships with person data...")
    cur.execute('''
        SELECT
            pr.person_id, pr.related_person_id, pr.strength,
            p1.birth_year, p1.death_year, p1.floruit_start, p1.floruit_end,
            p2.birth_year, p2.death_year, p2.floruit_start, p2.floruit_end
        FROM person_relationships pr
        JOIN persons p1 ON pr.person_id = p1.id
        JOIN persons p2 ON pr.related_person_id = p2.id
    ''')
    relationships = cur.fetchall()
    print(f"Total relationships: {len(relationships):,}")

    # 공유 장소 인덱스 생성 (기존 관계에 대해서만)
    print("\nBuilding shared location index for existing relationships...")

    # 기존 관계의 person_id 쌍 추출
    relationship_pairs = set()
    for row in relationships:
        p1, p2 = row[0], row[1]
        relationship_pairs.add((min(p1, p2), max(p1, p2)))

    # 배치로 공유 장소 조회
    shared_locations = {}
    batch_size = 1000
    pairs_list = list(relationship_pairs)

    for i in range(0, len(pairs_list), batch_size):
        batch = pairs_list[i:i+batch_size]
        # 배치 내 person_ids
        person_ids = set()
        for p1, p2 in batch:
            person_ids.add(p1)
            person_ids.add(p2)

        if not person_ids:
            continue

        # 해당 인물들의 장소 조회
        cur.execute('''
            SELECT person_id, location_id
            FROM person_locations
            WHERE person_id = ANY(%s)
        ''', (list(person_ids),))

        # person -> locations 매핑
        person_locs = {}
        for pid, lid in cur.fetchall():
            if pid not in person_locs:
                person_locs[pid] = set()
            person_locs[pid].add(lid)

        # 배치 내 쌍의 공유 장소 계산
        for p1, p2 in batch:
            locs1 = person_locs.get(p1, set())
            locs2 = person_locs.get(p2, set())
            shared = len(locs1 & locs2)
            if shared > 0:
                shared_locations[(p1, p2)] = shared

        if (i + batch_size) % 10000 == 0:
            print(f"  Progress: {min(i+batch_size, len(pairs_list)):,} / {len(pairs_list):,}")

    print(f"Pairs with shared locations: {len(shared_locations):,}")

    # 강도 재계산
    print("\nCalculating new strengths...")
    updates = []

    for row in relationships:
        person_id, related_id, current_strength = row[:3]
        p1_birth, p1_death, p1_floruit_start, p1_floruit_end = row[3:7]
        p2_birth, p2_death, p2_floruit_start, p2_floruit_end = row[7:11]

        # floruit 우선 사용
        p1_b = p1_floruit_start or p1_birth
        p1_d = p1_floruit_end or p1_death
        p2_b = p2_floruit_start or p2_birth
        p2_d = p2_floruit_end or p2_death

        # 1. Source factor (current strength = shared source count)
        source_factor = calculate_source_factor(current_strength)

        # 2. Location factor
        key = (min(person_id, related_id), max(person_id, related_id))
        loc_count = shared_locations.get(key, 0)
        location_factor = loc_count * 2.0

        # 3. Temporal factor
        temporal_score, time_dist = calculate_temporal_overlap(p1_b, p1_d, p2_b, p2_d)

        # 최종 강도
        new_strength = source_factor + location_factor + temporal_score
        new_strength = max(0.1, new_strength)  # 최소값 보장

        updates.append((new_strength, time_dist, person_id, related_id))

    # 분포 출력
    strengths = [u[0] for u in updates]
    print(f"\n강도 분포:")
    print(f"  최소: {min(strengths):.1f}")
    print(f"  최대: {max(strengths):.1f}")
    print(f"  평균: {sum(strengths)/len(strengths):.1f}")
    print(f"  강함 (>=10): {len([s for s in strengths if s >= 10]):,}개")
    print(f"  매우 강함 (>=30): {len([s for s in strengths if s >= 30]):,}개")
    print(f"  약함 (<5): {len([s for s in strengths if s < 5]):,}개")

    if not dry_run:
        print("\nUpdating database...")
        batch_size = 5000
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            cur.executemany('''
                UPDATE person_relationships
                SET strength = %s, time_distance = %s
                WHERE person_id = %s AND related_person_id = %s
            ''', batch)
            conn.commit()
            if (i + batch_size) % 50000 == 0 or i + batch_size >= len(updates):
                print(f"  Progress: {min(i+batch_size, len(updates)):,} / {len(updates):,}")

        print("\n[완료] 강도 업데이트 완료")

    # 샘플 출력
    print("\n=== 상위 10개 관계 (새 강도) ===")
    top_updates = sorted(updates, key=lambda x: x[0], reverse=True)[:10]
    for strength, time_dist, p1, p2 in top_updates:
        cur.execute('''
            SELECT p1.name, p2.name
            FROM persons p1, persons p2
            WHERE p1.id = %s AND p2.id = %s
        ''', (p1, p2))
        names = cur.fetchone()
        print(f"  {names[0]} <-> {names[1]}: {strength:.1f}")

    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--execute', action='store_true', help='Actually update')
    args = parser.parse_args()

    if args.execute:
        update_strengths(dry_run=False)
    else:
        update_strengths(dry_run=True)
        print("\n[!] --execute 플래그로 실제 업데이트 실행")


if __name__ == '__main__':
    main()
