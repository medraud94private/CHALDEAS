#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person-Event 연결 스크립트 (text_mentions 공유 소스 기반)

text_mentions 테이블에서 동일 source_id를 공유하는 person과 event를
event_persons 테이블에 연결합니다.
"""

import sys
import argparse
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from psycopg2.extras import execute_batch


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def link_persons_to_events(mention_count=None, batch_size=5000, dry_run=False):
    """
    text_mentions에서 동일 source를 공유하는 person-event 쌍을 찾아 연결합니다.

    Args:
        mention_count: 특정 mention_count인 persons만 처리 (None=전체)
        batch_size: 배치 크기
        dry_run: True면 실제 INSERT 없이 카운트만
    """
    print("=" * 60)
    print("Person-Event Linking via Shared Sources")
    print(f"mention_count filter: {mention_count}")
    print(f"dry_run: {dry_run}")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # Build query based on mention_count filter
    mention_filter = ""
    if mention_count is not None:
        if mention_count == 0:
            mention_filter = "AND p.mention_count = 0"
        elif mention_count >= 2:
            mention_filter = f"AND p.mention_count >= {mention_count}"
        else:
            mention_filter = f"AND p.mention_count = {mention_count}"

    # Find person-event pairs sharing sources
    print("\nFinding person-event pairs...")

    query = f"""
        SELECT DISTINCT pm.entity_id as person_id, em.entity_id as event_id
        FROM text_mentions pm
        JOIN text_mentions em ON pm.source_id = em.source_id
        JOIN persons p ON pm.entity_id = p.id
        JOIN events e ON em.entity_id = e.id
        WHERE pm.entity_type = 'person'
        AND em.entity_type = 'event'
        {mention_filter}
    """

    cur.execute(query)
    pairs = cur.fetchall()
    print(f"Found {len(pairs):,} person-event pairs")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        conn.close()
        return len(pairs)

    # Get existing links to avoid duplicates
    print("\nChecking existing links...")
    cur.execute("SELECT event_id, person_id FROM event_persons")
    existing = set(cur.fetchall())
    print(f"Existing links: {len(existing):,}")

    # Filter out existing pairs
    new_pairs = [(eid, pid) for pid, eid in pairs if (eid, pid) not in existing]
    print(f"New pairs to insert: {len(new_pairs):,}")

    if not new_pairs:
        print("\nNo new links to create.")
        conn.close()
        return 0

    # Insert in batches
    print(f"\nInserting {len(new_pairs):,} links in batches of {batch_size}...")

    insert_query = """
        INSERT INTO event_persons (event_id, person_id, role)
        VALUES (%s, %s, 'mentioned')
        ON CONFLICT DO NOTHING
    """

    total_inserted = 0
    for i in range(0, len(new_pairs), batch_size):
        batch = [(eid, pid, 'mentioned') for eid, pid in new_pairs[i:i+batch_size]]
        cur.executemany(
            "INSERT INTO event_persons (event_id, person_id, role) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            batch
        )
        total_inserted += cur.rowcount
        conn.commit()

        if (i + batch_size) % 50000 == 0 or i + batch_size >= len(new_pairs):
            print(f"  Progress: {min(i+batch_size, len(new_pairs)):,} / {len(new_pairs):,} ({total_inserted:,} inserted)")

    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM event_persons")
    total_links = cur.fetchone()[0]

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Links inserted: {total_inserted:,}")
    print(f"Total event_persons now: {total_links:,}")

    conn.close()
    return total_inserted


def main():
    parser = argparse.ArgumentParser(description='Link persons to events via shared sources')
    parser.add_argument('--mention', type=int, help='Filter by mention_count (1, 2, etc.)')
    parser.add_argument('--mention-min', type=int, help='Filter by minimum mention_count')
    parser.add_argument('--all', action='store_true', help='Process all persons')
    parser.add_argument('--dry-run', action='store_true', help='Count only, no insert')
    parser.add_argument('--batch-size', type=int, default=5000, help='Batch size for inserts')

    args = parser.parse_args()

    if args.all:
        link_persons_to_events(mention_count=None, batch_size=args.batch_size, dry_run=args.dry_run)
    elif args.mention_min:
        link_persons_to_events(mention_count=args.mention_min, batch_size=args.batch_size, dry_run=args.dry_run)
    elif args.mention is not None:
        link_persons_to_events(mention_count=args.mention, batch_size=args.batch_size, dry_run=args.dry_run)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python link_persons_events_via_source.py --mention 1")
        print("  python link_persons_events_via_source.py --mention-min 2")
        print("  python link_persons_events_via_source.py --all")
        print("  python link_persons_events_via_source.py --all --dry-run")


if __name__ == '__main__':
    main()
