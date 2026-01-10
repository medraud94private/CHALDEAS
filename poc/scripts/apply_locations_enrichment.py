#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Location 엔리치먼트 결과를 DB에 적용하는 스크립트

사용법:
    python apply_locations_enrichment.py --dry-run    # 미리보기
    python apply_locations_enrichment.py --apply      # 실제 적용
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

# Default results file
DEFAULT_RESULTS_FILE = Path(__file__).parent.parent / "data" / "enrichment_results" / "locations_20260110_201801.json"


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def backup_locations_table(conn):
    """Create backup of locations table."""
    cur = conn.cursor()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"locations_backup_{timestamp}"

    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM locations")
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]

    print(f"Backup created: {backup_table} ({count:,} rows)")
    return backup_table


def load_enrichment_results(file_path):
    """Load enrichment results from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter out errors
    results = [r for r in data['results'] if 'error' not in r]
    print(f"Loaded: {len(results):,} results (errors excluded)")
    return results


def apply_enrichment(conn, results, dry_run=True):
    """Apply enrichment results to locations table."""
    # Use autocommit to avoid rollback issues
    conn.autocommit = True
    cur = conn.cursor()

    updated = 0
    skipped = 0
    null_type_count = 0
    errors = 0

    for result in results:
        loc_id = result.get('id')
        if not loc_id:
            skipped += 1
            continue

        country = result.get('country')
        region = result.get('region')
        loc_type = result.get('type')

        # Handle array results (some LLM responses return arrays)
        if isinstance(country, list):
            country = country[0] if country else None
        if isinstance(region, list):
            region = region[0] if region else None
        if isinstance(loc_type, list):
            loc_type = loc_type[0] if loc_type else None

        # Truncate to column limits
        if country and len(country) > 100:
            country = country[:100]
        if region and len(region) > 100:
            region = region[:100]
        if loc_type and len(loc_type) > 50:
            loc_type = loc_type[:50]

        # Skip if no useful data
        if not country and not region and not loc_type:
            skipped += 1
            continue

        if loc_type is None:
            null_type_count += 1

        if dry_run:
            if updated < 5:
                print(f"  [{loc_id}] {result.get('name', 'N/A')[:40]}")
                print(f"       country={country}, region={region}, type={loc_type}")
            updated += 1
        else:
            try:
                # Use COALESCE to keep existing type if new type is NULL
                cur.execute('''
                    UPDATE locations
                    SET country = COALESCE(%s, country),
                        region = COALESCE(%s, region),
                        type = COALESCE(%s, type),
                        geocoded_by = 'gpt-5.1',
                        geocoded_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                ''', (country, region, loc_type, loc_id))
                updated += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Error id={loc_id}: {str(e)[:60]}")
                skipped += 1
                continue

        if updated % 5000 == 0 and updated > 0:
            print(f"  Progress: {updated:,} updated...")

    conn.autocommit = False

    return updated, skipped, null_type_count


def main():
    parser = argparse.ArgumentParser(description='Location 엔리치먼트 결과 DB 적용')
    parser.add_argument('--dry-run', action='store_true', help='미리보기 (실제 적용 안함)')
    parser.add_argument('--apply', action='store_true', help='실제 DB에 적용')
    parser.add_argument('--no-backup', action='store_true', help='백업 생성 안함')
    parser.add_argument('--file', type=str, help='엔리치먼트 결과 파일 경로')

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Usage:")
        print("  python apply_locations_enrichment.py --dry-run    # Preview")
        print("  python apply_locations_enrichment.py --apply      # Apply")
        return

    results_file = Path(args.file) if args.file else DEFAULT_RESULTS_FILE

    print(f"\n=== Location Enrichment Apply ===")
    print(f"File: {results_file}")
    print(f"Mode: {'DRY-RUN (preview)' if args.dry_run else 'APPLY (실제 적용)'}\n")

    if not results_file.exists():
        print(f"Error: File not found: {results_file}")
        return

    # Load results
    results = load_enrichment_results(results_file)

    # Connect to DB
    conn = get_db_connection()

    try:
        # Create backup if applying
        if args.apply and not args.no_backup:
            backup_locations_table(conn)

        # Apply enrichment
        updated, skipped, null_type = apply_enrichment(conn, results, dry_run=args.dry_run)

        print(f"\n=== Results ===")
        print(f"Updated: {updated:,}")
        print(f"Skipped: {skipped:,}")
        print(f"NULL type (kept existing): {null_type:,}")

        if args.dry_run:
            print(f"\n[DRY-RUN] To apply: python apply_locations_enrichment.py --apply")
        else:
            # Show final stats
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(country) as with_country,
                    COUNT(region) as with_region
                FROM locations
            """)
            row = cur.fetchone()
            print(f"\nFinal DB status:")
            print(f"  Total locations: {row[0]:,}")
            print(f"  With country: {row[1]:,} ({100*row[1]/row[0]:.1f}%)")
            print(f"  With region: {row[2]:,} ({100*row[2]/row[0]:.1f}%)")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
