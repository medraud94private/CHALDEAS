#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person-Person 관계 연결 스크립트 (text_mentions 공유 소스 기반)

공유 source 수가 min_shared 이상인 인물 쌍을 person_relationships에 연결합니다.
strength = 공유 source 수
"""

import sys
import argparse

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


def link_persons(min_shared=2):
    print("=" * 60)
    print("Person-Person Linking via Shared Sources")
    print(f"Minimum shared sources: {min_shared}")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # Find person pairs with shared source counts
    print("\nFinding person-person pairs...")
    cur.execute("""
        SELECT
            LEAST(p1.entity_id, p2.entity_id) as person1_id,
            GREATEST(p1.entity_id, p2.entity_id) as person2_id,
            COUNT(DISTINCT p1.source_id) as shared_count
        FROM text_mentions p1
        JOIN text_mentions p2 ON p1.source_id = p2.source_id
        WHERE p1.entity_type = 'person'
        AND p2.entity_type = 'person'
        AND p1.entity_id < p2.entity_id
        GROUP BY person1_id, person2_id
        HAVING COUNT(DISTINCT p1.source_id) >= %s
    """, (min_shared,))
    pairs = cur.fetchall()
    print(f"Found {len(pairs):,} person-person pairs")

    # Get existing
    cur.execute("SELECT person_id, related_person_id FROM person_relationships")
    existing = set()
    for row in cur.fetchall():
        existing.add((min(row[0], row[1]), max(row[0], row[1])))
    print(f"Existing relationships: {len(existing):,}")

    new_pairs = [(p1, p2, cnt) for p1, p2, cnt in pairs if (p1, p2) not in existing]
    print(f"New pairs to insert: {len(new_pairs):,}")

    if not new_pairs:
        print("\nNo new relationships to create.")
        conn.close()
        return

    # Insert
    print(f"\nInserting {len(new_pairs):,} relationships...")
    batch_size = 5000
    total = 0
    for i in range(0, len(new_pairs), batch_size):
        batch = new_pairs[i:i+batch_size]
        cur.executemany(
            """INSERT INTO person_relationships
               (person_id, related_person_id, relationship_type, strength, is_bidirectional)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            [(p1, p2, 'co_mentioned', cnt, 1) for p1, p2, cnt in batch]
        )
        total += cur.rowcount
        conn.commit()
        if (i + batch_size) % 50000 == 0 or i + batch_size >= len(new_pairs):
            print(f"  Progress: {min(i+batch_size, len(new_pairs)):,} / {len(new_pairs):,}")

    cur.execute("SELECT COUNT(*) FROM person_relationships")
    final = cur.fetchone()[0]

    print("\n" + "=" * 60)
    print(f"Relationships inserted: {total:,}")
    print(f"Total person_relationships: {final:,}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Link persons via shared sources')
    parser.add_argument('--min-shared', type=int, default=2,
                        help='Minimum shared sources (default: 2)')
    args = parser.parse_args()
    link_persons(min_shared=args.min_shared)


if __name__ == '__main__':
    main()
