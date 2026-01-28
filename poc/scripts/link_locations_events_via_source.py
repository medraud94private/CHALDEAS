#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Location-Event 연결 스크립트 (text_mentions 공유 소스 기반)
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


def link_all():
    print("=" * 60)
    print("Location-Event Linking via Shared Sources")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # Find all location-event pairs sharing sources
    print("\nFinding location-event pairs...")
    cur.execute("""
        SELECT DISTINCT lm.entity_id as location_id, em.entity_id as event_id
        FROM text_mentions lm
        JOIN text_mentions em ON lm.source_id = em.source_id
        WHERE lm.entity_type = 'location'
        AND em.entity_type = 'event'
    """)
    pairs = cur.fetchall()
    print(f"Found {len(pairs):,} location-event pairs")

    # Get existing
    cur.execute("SELECT event_id, location_id FROM event_locations")
    existing = set(cur.fetchall())
    print(f"Existing links: {len(existing):,}")

    new_pairs = [(eid, lid) for lid, eid in pairs if (eid, lid) not in existing]
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
            "INSERT INTO event_locations (event_id, location_id, role) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(eid, lid, 'mentioned') for eid, lid in batch]
        )
        total += cur.rowcount
        conn.commit()
        if (i + batch_size) % 50000 == 0 or i + batch_size >= len(new_pairs):
            print(f"  Progress: {min(i+batch_size, len(new_pairs)):,} / {len(new_pairs):,}")

    cur.execute("SELECT COUNT(*) FROM event_locations")
    final = cur.fetchone()[0]

    print("\n" + "=" * 60)
    print(f"Links inserted: {total:,}")
    print(f"Total event_locations: {final:,}")
    conn.close()


if __name__ == '__main__':
    link_all()
