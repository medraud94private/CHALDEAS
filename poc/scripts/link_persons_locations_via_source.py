#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person-Location 연결 스크립트 (text_mentions 공유 소스 기반)

person_locations 테이블 생성 후 연결합니다.
"""

import sys
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


def create_table_if_not_exists(conn):
    """person_locations 테이블 생성."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS person_locations (
            person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
            role VARCHAR(50) DEFAULT 'associated',
            PRIMARY KEY (person_id, location_id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_person_locations_person
        ON person_locations(person_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_person_locations_location
        ON person_locations(location_id)
    """)
    conn.commit()
    print("Table person_locations created/verified")


def link_all():
    print("=" * 60)
    print("Person-Location Linking via Shared Sources")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # Create table
    create_table_if_not_exists(conn)

    # Find all person-location pairs sharing sources
    print("\nFinding person-location pairs...")
    cur.execute("""
        SELECT DISTINCT pm.entity_id as person_id, lm.entity_id as location_id
        FROM text_mentions pm
        JOIN text_mentions lm ON pm.source_id = lm.source_id
        WHERE pm.entity_type = 'person'
        AND lm.entity_type = 'location'
    """)
    pairs = cur.fetchall()
    print(f"Found {len(pairs):,} person-location pairs")

    # Get existing
    cur.execute("SELECT person_id, location_id FROM person_locations")
    existing = set(cur.fetchall())
    print(f"Existing links: {len(existing):,}")

    new_pairs = [(pid, lid) for pid, lid in pairs if (pid, lid) not in existing]
    print(f"New pairs to insert: {len(new_pairs):,}")

    if not new_pairs:
        print("\nNo new links to create.")
        conn.close()
        return

    # Insert
    print(f"\nInserting {len(new_pairs):,} links...")
    batch_size = 5000
    total = 0
    for i in range(0, len(new_pairs), batch_size):
        batch = new_pairs[i:i+batch_size]
        cur.executemany(
            "INSERT INTO person_locations (person_id, location_id, role) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(pid, lid, 'associated') for pid, lid in batch]
        )
        total += cur.rowcount
        conn.commit()
        if (i + batch_size) % 100000 == 0 or i + batch_size >= len(new_pairs):
            print(f"  Progress: {min(i+batch_size, len(new_pairs)):,} / {len(new_pairs):,}")

    cur.execute("SELECT COUNT(*) FROM person_locations")
    final = cur.fetchone()[0]

    print("\n" + "=" * 60)
    print(f"Links inserted: {total:,}")
    print(f"Total person_locations: {final:,}")
    conn.close()


if __name__ == '__main__':
    link_all()
