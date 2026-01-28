"""
Event Deduplication Script

Removes exact duplicate events (same title + same date_start).
Preserves the record with the most complete data.

Usage:
    python poc/scripts/deduplicate_events.py --dry-run       # Preview only
    python poc/scripts/deduplicate_events.py --execute       # Actually delete
    python poc/scripts/deduplicate_events.py --limit 100     # Test with small batch
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import text
from app.db.session import SessionLocal


def calculate_record_quality(event: dict) -> int:
    """
    Calculate quality score for a record.
    Higher score = better record to keep.
    """
    score = 0

    # Description (most important)
    if event['description']:
        score += len(event['description']) // 10  # Up to ~50 points
        score = min(score, 50)

    # External links
    if event['wikipedia_url']:
        score += 50  # Wikipedia link is very valuable
    if event['image_url']:
        score += 20

    # Importance score
    if event['importance']:
        score += event['importance'] * 10

    # Relations count
    score += event['person_count'] * 5
    score += event['location_count'] * 5

    # Has primary location
    if event['primary_location_id']:
        score += 10

    # Korean translation
    if event['title_ko']:
        score += 5
    if event['description_ko']:
        score += 5

    return score


def find_duplicates(db) -> dict:
    """
    Find all duplicate events (same title + date_start).
    Returns: {(title, date_start): [event_ids]}
    """
    query = text("""
        SELECT
            e.id,
            e.title,
            e.title_ko,
            e.date_start,
            e.description,
            e.description_ko,
            e.wikipedia_url,
            e.image_url,
            e.importance,
            e.primary_location_id,
            COALESCE((SELECT COUNT(*) FROM event_persons WHERE event_id = e.id), 0) as person_count,
            COALESCE((SELECT COUNT(*) FROM event_locations WHERE event_id = e.id), 0) as location_count
        FROM events e
        WHERE (e.title, e.date_start) IN (
            SELECT title, date_start
            FROM events
            GROUP BY title, date_start
            HAVING COUNT(*) > 1
        )
        ORDER BY e.title, e.date_start, e.id
    """)

    result = db.execute(query)

    duplicates = defaultdict(list)
    for row in result:
        key = (row.title, row.date_start)
        duplicates[key].append({
            'id': row.id,
            'title': row.title,
            'title_ko': row.title_ko,
            'date_start': row.date_start,
            'description': row.description,
            'description_ko': row.description_ko,
            'wikipedia_url': row.wikipedia_url,
            'image_url': row.image_url,
            'importance': row.importance,
            'primary_location_id': row.primary_location_id,
            'person_count': row.person_count,
            'location_count': row.location_count,
        })

    return duplicates


def merge_relations(db, keep_id: int, delete_ids: list, dry_run: bool = True):
    """
    Transfer relations from deleted records to the kept record.
    """
    if dry_run:
        return

    for delete_id in delete_ids:
        # Transfer event_persons
        db.execute(text("""
            INSERT INTO event_persons (event_id, person_id, role)
            SELECT :keep_id, person_id, role
            FROM event_persons
            WHERE event_id = :delete_id
            ON CONFLICT DO NOTHING
        """), {'keep_id': keep_id, 'delete_id': delete_id})

        # Transfer event_locations
        db.execute(text("""
            INSERT INTO event_locations (event_id, location_id, role)
            SELECT :keep_id, location_id, role
            FROM event_locations
            WHERE event_id = :delete_id
            ON CONFLICT DO NOTHING
        """), {'keep_id': keep_id, 'delete_id': delete_id})


def delete_duplicates(db, delete_ids: list, dry_run: bool = True):
    """
    Delete duplicate events.
    """
    if dry_run or not delete_ids:
        return

    # Delete in batches
    for event_id in delete_ids:
        # First delete relations
        db.execute(text("DELETE FROM event_persons WHERE event_id = :id"), {'id': event_id})
        db.execute(text("DELETE FROM event_locations WHERE event_id = :id"), {'id': event_id})

        # Then delete event
        db.execute(text("DELETE FROM events WHERE id = :id"), {'id': event_id})


def main():
    parser = argparse.ArgumentParser(description="Deduplicate events")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't delete")
    parser.add_argument("--execute", action="store_true", help="Actually perform deletion")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of groups to process")
    parser.add_argument("--output", type=str, default=None, help="Save report to JSON file")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("ERROR: Must specify either --dry-run or --execute")
        print("Use --dry-run first to preview changes")
        return 1

    dry_run = not args.execute

    print("=" * 60)
    print("EVENT DEDUPLICATION SCRIPT")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (will delete!)'}")
    print()

    db = SessionLocal()

    try:
        print("Finding duplicates...")
        duplicates = find_duplicates(db)

        total_groups = len(duplicates)
        total_duplicates = sum(len(events) - 1 for events in duplicates.values())

        print(f"Found {total_groups} duplicate groups")
        print(f"Total records to delete: {total_duplicates}")
        print()

        if args.limit:
            # Limit for testing
            items = list(duplicates.items())[:args.limit]
            duplicates = dict(items)
            print(f"[Limited to {args.limit} groups for testing]")
            print()

        # Process each group
        report = []
        to_delete = []

        for (title, date_start), events in duplicates.items():
            # Calculate quality scores
            for event in events:
                event['quality_score'] = calculate_record_quality(event)

            # Sort by quality (highest first)
            events.sort(key=lambda x: x['quality_score'], reverse=True)

            keep = events[0]
            delete = events[1:]

            year_str = f"BCE {-date_start}" if date_start < 0 else str(date_start)

            group_report = {
                'title': title,
                'year': year_str,
                'keep_id': keep['id'],
                'keep_score': keep['quality_score'],
                'delete_ids': [e['id'] for e in delete],
                'delete_count': len(delete)
            }
            report.append(group_report)

            to_delete.extend([e['id'] for e in delete])

            # Print details for large duplicates
            if len(events) >= 5:
                print(f"[{len(events)}x] {title} ({year_str})")
                print(f"  Keep: ID {keep['id']} (score: {keep['quality_score']})")
                print(f"  Delete: {len(delete)} records")

        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Groups processed: {len(report)}")
        print(f"Records to keep: {len(report)}")
        print(f"Records to delete: {len(to_delete)}")
        print()

        # Top duplicates
        top_dups = sorted(report, key=lambda x: x['delete_count'], reverse=True)[:10]
        print("Top 10 largest duplicate groups:")
        for r in top_dups:
            print(f"  {r['title']} ({r['year']}): {r['delete_count'] + 1} copies -> keeping ID {r['keep_id']}")
        print()

        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'dry_run' if dry_run else 'execute',
                    'total_groups': len(report),
                    'total_to_delete': len(to_delete),
                    'groups': report
                }, f, ensure_ascii=False, indent=2)
            print(f"Report saved to: {output_path}")

        if not dry_run:
            print("EXECUTING DELETION...")

            # Merge relations first
            print("  Merging relations...")
            for r in report:
                merge_relations(db, r['keep_id'], r['delete_ids'], dry_run=False)

            # Delete duplicates
            print("  Deleting duplicates...")
            delete_duplicates(db, to_delete, dry_run=False)

            # Commit
            db.commit()
            print(f"  DONE! Deleted {len(to_delete)} duplicate events.")
        else:
            print("DRY RUN complete. Use --execute to perform actual deletion.")
            print("Recommended: backup database first!")
            print("  pg_dump -U chaldeas -d chaldeas > backup.sql")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
