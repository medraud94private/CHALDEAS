#!/usr/bin/env python3
"""
중복 이벤트 병합 알고리즘

같은 시대 + 유사 장소 + 유사 내용인 이벤트를 찾아서 병합.
벡터 유사도 + 연도 + 위치로 중복 판단.
"""
import sys
import os
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

SIMILARITY_THRESHOLD = 0.92  # 임베딩 유사도 (높을수록 엄격)
YEAR_TOLERANCE = 5  # 연도 차이 허용범위


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def find_duplicates(conn):
    """벡터 유사도로 중복 후보 찾기"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 임베딩 있는 이벤트만
    cur.execute("""
        SELECT id, title, date_start, primary_location_id,
               description, category_id, embedding
        FROM events
        WHERE embedding IS NOT NULL
        ORDER BY date_start, id
    """)
    events = cur.fetchall()
    print(f"Total events with embedding: {len(events):,}")

    # 연도별로 그룹핑 (성능 최적화)
    by_year = defaultdict(list)
    for e in events:
        if e['date_start']:
            by_year[e['date_start']].append(e)

    duplicates = []
    checked = set()

    for year, year_events in by_year.items():
        if len(year_events) < 2:
            continue

        # 같은 연도 내에서 유사도 체크
        for i, e1 in enumerate(year_events):
            if e1['id'] in checked:
                continue

            for e2 in year_events[i+1:]:
                if e2['id'] in checked:
                    continue

                # 같은 위치인지 체크
                same_loc = (e1['primary_location_id'] == e2['primary_location_id']
                           and e1['primary_location_id'] is not None)

                if not same_loc:
                    continue

                # 벡터 유사도 계산 (PostgreSQL에서)
                cur.execute("""
                    SELECT 1 - (e1.embedding <=> e2.embedding) as similarity
                    FROM events e1, events e2
                    WHERE e1.id = %s AND e2.id = %s
                """, (e1['id'], e2['id']))

                result = cur.fetchone()
                if result and result['similarity'] >= SIMILARITY_THRESHOLD:
                    duplicates.append({
                        'id1': e1['id'],
                        'id2': e2['id'],
                        'title1': e1['title'],
                        'title2': e2['title'],
                        'year': year,
                        'similarity': result['similarity']
                    })
                    checked.add(e2['id'])

    return duplicates


def merge_events(conn, dup):
    """두 이벤트를 병합 (더 긴 설명을 가진 쪽으로)"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 두 이벤트 조회
    cur.execute("SELECT * FROM events WHERE id IN (%s, %s)", (dup['id1'], dup['id2']))
    events = {e['id']: e for e in cur.fetchall()}

    e1, e2 = events[dup['id1']], events[dup['id2']]

    # 더 좋은 데이터 결정 (설명이 긴 쪽)
    len1 = len(e1['description'] or '')
    len2 = len(e2['description'] or '')

    keep, remove = (e1, e2) if len1 >= len2 else (e2, e1)

    # 병합: 빈 필드 채우기
    updates = []
    if not keep['description'] and remove['description']:
        updates.append(f"description = '{remove['description']}'")
    if not keep['category_id'] and remove['category_id']:
        updates.append(f"category_id = {remove['category_id']}")
    if not keep['primary_location_id'] and remove['primary_location_id']:
        updates.append(f"primary_location_id = {remove['primary_location_id']}")
    if not keep['wikipedia_url'] and remove.get('wikipedia_url'):
        updates.append(f"wikipedia_url = '{remove['wikipedia_url']}'")

    # 업데이트 실행
    if updates:
        cur.execute(f"UPDATE events SET {', '.join(updates)} WHERE id = %s", (keep['id'],))

    # 관계 이전 (event_persons, event_locations)
    try:
        cur.execute("""
            UPDATE event_persons SET event_id = %s
            WHERE event_id = %s AND event_id != %s
        """, (keep['id'], remove['id'], keep['id']))
    except:
        pass

    try:
        cur.execute("""
            UPDATE event_locations SET event_id = %s
            WHERE event_id = %s AND event_id != %s
        """, (keep['id'], remove['id'], keep['id']))
    except:
        pass

    # 중복 삭제
    cur.execute("DELETE FROM events WHERE id = %s", (remove['id'],))

    return keep['id'], remove['id']


def main():
    print("=" * 60)
    print("중복 이벤트 병합")
    print(f"유사도 임계값: {SIMILARITY_THRESHOLD}")
    print(f"연도 허용 범위: ±{YEAR_TOLERANCE}년")
    print("=" * 60)

    conn = get_db_connection()
    print("Database connected!")

    # 중복 찾기
    print("\n중복 후보 검색 중...")
    duplicates = find_duplicates(conn)
    print(f"발견된 중복: {len(duplicates)}쌍")

    if not duplicates:
        print("중복 없음!")
        return

    # 샘플 출력
    print("\n샘플 중복:")
    for d in duplicates[:5]:
        print(f"  [{d['year']}] {d['title1'][:30]}... ↔ {d['title2'][:30]}... (sim: {d['similarity']:.3f})")

    # 병합 실행
    print(f"\n{len(duplicates)}개 병합 중...")
    merged = 0
    for d in duplicates:
        try:
            keep_id, remove_id = merge_events(conn, d)
            merged += 1
            if merged % 50 == 0:
                conn.commit()
                print(f"  병합됨: {merged}/{len(duplicates)}")
        except Exception as e:
            conn.rollback()
            continue

    conn.commit()

    print()
    print("=" * 60)
    print(f"병합 완료: {merged}개")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
