#!/usr/bin/env python3
"""
같은 사건 연결 알고리즘

같은 역사적 사건을 다른 출처에서 서술한 이벤트들을 연결.
삭제하지 않고 event_aliases 테이블로 관계 저장.
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

SIMILARITY_THRESHOLD = 0.90  # 임베딩 유사도 기준


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def ensure_alias_table(conn):
    """event_aliases 테이블 생성"""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_aliases (
            id SERIAL PRIMARY KEY,
            event_id_1 INT REFERENCES events(id) ON DELETE CASCADE,
            event_id_2 INT REFERENCES events(id) ON DELETE CASCADE,
            similarity FLOAT,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(event_id_1, event_id_2)
        )
    """)

    # 인덱스
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_aliases_1 ON event_aliases(event_id_1)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_aliases_2 ON event_aliases(event_id_2)
    """)
    conn.commit()
    print("event_aliases 테이블 준비됨")


def find_same_events(conn):
    """같은 사건인 이벤트 쌍 찾기"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 이미 연결된 쌍 조회
    cur.execute("SELECT event_id_1, event_id_2 FROM event_aliases")
    existing = {(r['event_id_1'], r['event_id_2']) for r in cur.fetchall()}
    existing.update({(r[1], r[0]) for r in existing})  # 양방향

    # 연도별 이벤트 그룹핑
    cur.execute("""
        SELECT id, title, date_start, primary_location_id
        FROM events
        WHERE embedding IS NOT NULL AND date_start IS NOT NULL
        ORDER BY date_start
    """)
    events = cur.fetchall()
    print(f"이벤트 수: {len(events):,}")

    by_year = defaultdict(list)
    for e in events:
        by_year[e['date_start']].append(e)

    same_events = []

    for year, year_events in by_year.items():
        if len(year_events) < 2:
            continue

        for i, e1 in enumerate(year_events):
            for e2 in year_events[i+1:]:
                # 이미 연결됐으면 스킵
                if (e1['id'], e2['id']) in existing:
                    continue

                # 같은 위치 체크 (있으면)
                same_loc = (e1['primary_location_id'] == e2['primary_location_id']
                           and e1['primary_location_id'] is not None)

                # 벡터 유사도 계산
                cur.execute("""
                    SELECT 1 - (e1.embedding <=> e2.embedding) as sim
                    FROM events e1, events e2
                    WHERE e1.id = %s AND e2.id = %s
                """, (e1['id'], e2['id']))

                result = cur.fetchone()
                sim = result['sim'] if result else 0

                # 같은 위치면 유사도 기준 낮춤
                threshold = SIMILARITY_THRESHOLD - 0.05 if same_loc else SIMILARITY_THRESHOLD

                if sim >= threshold:
                    same_events.append({
                        'id1': min(e1['id'], e2['id']),
                        'id2': max(e1['id'], e2['id']),
                        'title1': e1['title'],
                        'title2': e2['title'],
                        'year': year,
                        'similarity': sim,
                        'same_location': same_loc
                    })

    return same_events


def save_aliases(conn, same_events):
    """연결 정보 저장"""
    cur = conn.cursor()
    saved = 0

    for pair in same_events:
        try:
            cur.execute("""
                INSERT INTO event_aliases (event_id_1, event_id_2, similarity)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (pair['id1'], pair['id2'], pair['similarity']))
            saved += 1
        except:
            conn.rollback()
            continue

        if saved % 100 == 0:
            conn.commit()
            print(f"  저장됨: {saved}/{len(same_events)}")

    conn.commit()
    return saved


def main():
    print("=" * 60)
    print("같은 사건 연결 (다른 출처)")
    print(f"유사도 기준: {SIMILARITY_THRESHOLD}")
    print("=" * 60)

    conn = get_db_connection()
    print("Database connected!")

    # 테이블 준비
    ensure_alias_table(conn)

    # 같은 사건 찾기
    print("\n같은 사건 검색 중...")
    same_events = find_same_events(conn)
    print(f"발견: {len(same_events)}쌍")

    if not same_events:
        print("새로운 연결 없음!")
        conn.close()
        return

    # 샘플 출력
    print("\nSamples:")
    for p in same_events[:10]:
        loc = "[LOC]" if p['same_location'] else ""
        try:
            print(f"  [{p['year']}] {p['title1'][:25]}... <-> {p['title2'][:25]}... {loc} ({p['similarity']:.2f})")
        except:
            print(f"  [{p['year']}] (encoding error) ({p['similarity']:.2f})")

    # 저장
    print(f"\n{len(same_events)}개 연결 저장 중...")
    saved = save_aliases(conn, same_events)

    print()
    print("=" * 60)
    print(f"저장 완료: {saved}개 연결")
    print("=" * 60)

    # 통계
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM event_aliases")
    total = cur.fetchone()[0]
    print(f"총 연결된 사건 쌍: {total}")

    conn.close()


if __name__ == "__main__":
    main()
