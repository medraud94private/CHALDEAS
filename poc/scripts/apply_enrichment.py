#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
엔리치먼트 결과를 DB에 적용하는 스크립트

사용법:
    python apply_enrichment.py --dry-run    # 미리보기
    python apply_enrichment.py --apply      # 실제 적용
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from psycopg2.extras import execute_values

# Configuration
RESULTS_FILE = Path(__file__).parent.parent / "data" / "enrichment_results" / "full_sync_20260108_181800.json"


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def backup_events_table(conn):
    """Create backup of events table."""
    cur = conn.cursor()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"events_backup_{timestamp}"

    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM events")
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]

    print(f"백업 생성: {backup_table} ({count}건)")
    return backup_table


def load_enrichment_results():
    """Load enrichment results from JSON file."""
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter out errors
    results = [r for r in data['results'] if 'error' not in r]
    print(f"로드된 결과: {len(results)}건 (에러 제외)")
    return results


def get_or_create_location(conn, result):
    """Get existing location or create new one based on enrichment data."""
    cur = conn.cursor()

    lat = result.get('latitude')
    lng = result.get('longitude')

    if lat is None or lng is None:
        return None

    # Try to find existing location by coordinates (within 0.1 degree)
    cur.execute("""
        SELECT id, name FROM locations
        WHERE ABS(latitude - %s) < 0.1 AND ABS(longitude - %s) < 0.1
        LIMIT 1
    """, (lat, lng))

    existing = cur.fetchone()
    if existing:
        return existing[0]

    # Create new location
    name = result.get('location_modern') or result.get('location_name') or 'Unknown'
    loc_type = result.get('location_type') or 'other'

    cur.execute("""
        INSERT INTO locations (name, latitude, longitude, type, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        RETURNING id
    """, (name[:255], lat, lng, loc_type))

    new_id = cur.fetchone()[0]
    return new_id


def apply_enrichment(conn, results, dry_run=True):
    """Apply enrichment results to events table."""
    cur = conn.cursor()

    updated = 0
    skipped = 0
    location_created = 0

    for result in results:
        event_id = result.get('id')
        if not event_id:
            skipped += 1
            continue

        # Prepare update fields
        updates = []
        params = []

        # Title
        if result.get('title_clean'):
            updates.append("title = %s")
            params.append(result['title_clean'][:255])

        # Dates (clamp to reasonable range: -100000 to 10000)
        MIN_YEAR = -100000
        MAX_YEAR = 10000

        year_start = result.get('year_start')
        if year_start is not None:
            if MIN_YEAR <= year_start <= MAX_YEAR:
                updates.append("date_start = %s")
                params.append(year_start)
            # else: skip unreasonable values

        year_end = result.get('year_end')
        if year_end is not None:
            if MIN_YEAR <= year_end <= MAX_YEAR:
                updates.append("date_end = %s")
                params.append(year_end)
            # else: skip unreasonable values

        # Date precision
        if result.get('year_precision'):
            updates.append("date_precision = %s")
            params.append(result['year_precision'])

        # Temporal scale
        if result.get('temporal_scale'):
            updates.append("temporal_scale = %s")
            params.append(result['temporal_scale'])

        # Certainty (from confidence)
        if result.get('confidence'):
            updates.append("certainty = %s")
            params.append(result['confidence'])

        # Location
        if not dry_run and (result.get('latitude') and result.get('longitude')):
            loc_id = get_or_create_location(conn, result)
            if loc_id:
                updates.append("primary_location_id = %s")
                params.append(loc_id)
                location_created += 1

        if updates:
            params.append(event_id)
            sql = f"UPDATE events SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s"

            if dry_run:
                if updated < 3:  # Show first 3 examples
                    print(f"\n[DRY-RUN] Event {event_id}:")
                    print(f"  Title: {result.get('title_clean', 'N/A')[:50]}")
                    print(f"  Year: {result.get('year_start')} ~ {result.get('year_end')}")
                    print(f"  Location: {result.get('location_modern', 'N/A')}")
            else:
                cur.execute(sql, params)

            updated += 1
        else:
            skipped += 1

        if updated % 1000 == 0 and updated > 0:
            print(f"  진행: {updated}건 처리됨...")

    if not dry_run:
        conn.commit()

    return updated, skipped, location_created


def main():
    parser = argparse.ArgumentParser(description='엔리치먼트 결과 DB 적용')
    parser.add_argument('--dry-run', action='store_true', help='미리보기 (실제 적용 안함)')
    parser.add_argument('--apply', action='store_true', help='실제 DB에 적용')
    parser.add_argument('--no-backup', action='store_true', help='백업 생성 안함')

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("사용법:")
        print("  python apply_enrichment.py --dry-run    # 미리보기")
        print("  python apply_enrichment.py --apply      # 실제 적용")
        return

    print(f"\n=== 엔리치먼트 결과 적용 ===")
    print(f"파일: {RESULTS_FILE}")
    print(f"모드: {'DRY-RUN (미리보기)' if args.dry_run else 'APPLY (실제 적용)'}\n")

    # Load results
    results = load_enrichment_results()

    # Connect to DB
    conn = get_db_connection()

    try:
        # Create backup if applying
        if args.apply and not args.no_backup:
            backup_events_table(conn)

        # Apply enrichment
        updated, skipped, loc_created = apply_enrichment(conn, results, dry_run=args.dry_run)

        print(f"\n=== 결과 ===")
        print(f"업데이트: {updated}건")
        print(f"스킵: {skipped}건")
        if not args.dry_run:
            print(f"위치 생성/연결: {loc_created}건")

        if args.dry_run:
            print("\n[DRY-RUN 완료] 실제 적용하려면: python apply_enrichment.py --apply")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
