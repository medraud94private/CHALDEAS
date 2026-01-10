#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Person 엔리치먼트 결과를 DB에 적용하는 스크립트

사용법:
    python apply_persons_enrichment.py --dry-run    # 미리보기
    python apply_persons_enrichment.py --apply      # 실제 적용
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

# Default results file - find latest
RESULTS_DIR = Path(__file__).parent.parent / "data" / "enrichment_results"


def get_latest_persons_file():
    """Find the latest persons enrichment result file."""
    files = list(RESULTS_DIR.glob("persons_*.json"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def backup_persons_table(conn):
    """Create backup of persons table."""
    cur = conn.cursor()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"persons_backup_{timestamp}"

    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM persons")
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]

    print(f"Backup created: {backup_table} ({count:,} rows)")
    return backup_table


def load_enrichment_results(file_path):
    """Load enrichment results from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter out errors and non-real persons
    results = [r for r in data['results']
               if 'error' not in r and r.get('is_real_person', True)]

    skipped_fictional = sum(1 for r in data['results']
                           if r.get('is_real_person') == False)

    print(f"Loaded: {len(results):,} real persons")
    print(f"Skipped: {skipped_fictional:,} fictional/non-persons")
    return results


def apply_enrichment(conn, results, dry_run=True):
    """Apply enrichment results to persons table."""
    # Commit any pending transaction before setting autocommit
    conn.commit()
    conn.autocommit = True
    cur = conn.cursor()

    updated = 0
    skipped = 0
    errors = 0

    for result in results:
        person_id = result.get('id')
        if not person_id:
            skipped += 1
            continue

        birth_year = result.get('birth_year')
        death_year = result.get('death_year')
        role = result.get('role')
        era = result.get('era')

        # Skip if no useful data
        if birth_year is None and death_year is None and not role and not era:
            skipped += 1
            continue

        # Truncate role/era if too long
        if role and len(role) > 100:
            role = role[:100]
        if era and len(era) > 50:
            era = era[:50]

        if dry_run:
            if updated < 5:
                print(f"  [{person_id}] {result.get('name', 'N/A')[:40]}")
                print(f"       birth={birth_year}, death={death_year}, role={role}, era={era}")
            updated += 1
        else:
            try:
                cur.execute('''
                    UPDATE persons
                    SET birth_year = COALESCE(%s, birth_year),
                        death_year = COALESCE(%s, death_year),
                        role = COALESCE(%s, role),
                        era = COALESCE(%s, era),
                        enriched_by = 'gpt-5.1',
                        enriched_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                ''', (birth_year, death_year, role, era, person_id))
                updated += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Error id={person_id}: {str(e)[:60]}")
                skipped += 1
                continue

        if updated % 500 == 0 and updated > 0:
            print(f"  Progress: {updated:,} updated...")

    conn.autocommit = False

    return updated, skipped, errors


def main():
    parser = argparse.ArgumentParser(description='Person 엔리치먼트 결과 DB 적용')
    parser.add_argument('--dry-run', action='store_true', help='미리보기 (실제 적용 안함)')
    parser.add_argument('--apply', action='store_true', help='실제 DB에 적용')
    parser.add_argument('--no-backup', action='store_true', help='백업 생성 안함')
    parser.add_argument('--file', type=str, help='엔리치먼트 결과 파일 경로')

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Usage:")
        print("  python apply_persons_enrichment.py --dry-run    # Preview")
        print("  python apply_persons_enrichment.py --apply      # Apply")
        return

    results_file = Path(args.file) if args.file else get_latest_persons_file()

    if not results_file or not results_file.exists():
        print(f"Error: No persons enrichment results found")
        return

    print(f"\n=== Person Enrichment Apply ===")
    print(f"File: {results_file}")
    print(f"Mode: {'DRY-RUN (preview)' if args.dry_run else 'APPLY (실제 적용)'}\n")

    # Load results
    results = load_enrichment_results(results_file)

    if not results:
        print("No results to apply!")
        return

    # Connect to DB
    conn = get_db_connection()

    try:
        # Create backup if applying
        if args.apply and not args.no_backup:
            backup_persons_table(conn)

        # Apply enrichment
        updated, skipped, errors = apply_enrichment(conn, results, dry_run=args.dry_run)

        print(f"\n=== Results ===")
        print(f"Updated: {updated:,}")
        print(f"Skipped: {skipped:,}")
        if errors:
            print(f"Errors: {errors:,}")

        if args.dry_run:
            print(f"\n[DRY-RUN] To apply: python apply_persons_enrichment.py --apply")
        else:
            # Show final stats
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(birth_year) as with_birth,
                    COUNT(death_year) as with_death,
                    COUNT(role) as with_role
                FROM persons
                WHERE mention_count >= 3
            """)
            row = cur.fetchone()
            print(f"\nFinal DB status (mention >= 10):")
            print(f"  Total: {row[0]:,}")
            print(f"  With birth_year: {row[1]:,} ({100*row[1]/row[0]:.1f}%)")
            print(f"  With death_year: {row[2]:,} ({100*row[2]/row[0]:.1f}%)")
            print(f"  With role: {row[3]:,} ({100*row[3]/row[0]:.1f}%)")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
