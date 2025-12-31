#!/usr/bin/env python3
"""
Enrich Events from Collected Data

Updates event descriptions using our already-collected data sources:
- wikidata_events.json
- worldhistory
- etc.

Usage:
    python data/scripts/processing/enrich_from_collected.py --dry-run
    python data/scripts/processing/enrich_from_collected.py --source wikidata
    python data/scripts/processing/enrich_from_collected.py --all
"""

import argparse
import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

DATA_DIR = Path(__file__).parent.parent.parent / "raw"


def get_db_connection():
    """Get database connection."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def normalize_name(name: str) -> str:
    """Normalize event name for matching."""
    # Lowercase
    name = name.lower()
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove common prefixes/suffixes
    name = re.sub(r'^the\s+', '', name)
    return name


def load_wikidata_events() -> Dict[str, dict]:
    """Load wikidata events indexed by normalized name."""
    filepath = DATA_DIR / "wikidata" / "wikidata_events.json"
    if not filepath.exists():
        print(f"  Warning: {filepath} not found")
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Index by normalized name
    indexed = {}
    for event in data:
        name = event.get('name', '')
        if name:
            key = normalize_name(name)
            # Keep the one with longer description
            new_desc = event.get('description') or ''
            old_desc = indexed.get(key, {}).get('description') or ''
            if key not in indexed or len(new_desc) > len(old_desc):
                indexed[key] = event

    print(f"  Loaded {len(indexed):,} events from wikidata")
    return indexed


def load_worldhistory_events() -> Dict[str, dict]:
    """Load worldhistory events."""
    dirpath = DATA_DIR / "worldhistory"
    if not dirpath.exists():
        return {}

    indexed = {}
    for filepath in dirpath.glob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        name = item.get('title') or item.get('name', '')
                        if name:
                            key = normalize_name(name)
                            indexed[key] = item
                elif isinstance(data, dict):
                    name = data.get('title') or data.get('name', '')
                    if name:
                        key = normalize_name(name)
                        indexed[key] = data
        except Exception as e:
            print(f"  Error loading {filepath}: {e}")

    print(f"  Loaded {len(indexed):,} events from worldhistory")
    return indexed


def get_events_needing_enrichment(conn, min_length: int = 50) -> List[dict]:
    """Get events with poor descriptions."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, title, description
        FROM events
        WHERE description IS NULL
           OR description = ''
           OR LENGTH(description) < %s
        ORDER BY LENGTH(COALESCE(description, ''))
    """, (min_length,))
    return cur.fetchall()


def update_event_description(conn, event_id: int, description: str, source: str):
    """Update event description and clear embedding."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE events
        SET description = %s,
            embedding = NULL,
            updated_at = NOW()
        WHERE id = %s
    """, (description, event_id))
    conn.commit()


def enrich_events(conn, sources: Dict[str, Dict[str, dict]], min_length: int = 50, dry_run: bool = False):
    """Enrich events from collected sources."""
    events = get_events_needing_enrichment(conn, min_length)
    print(f"\nEvents needing enrichment: {len(events):,}")

    enriched = 0
    not_found = 0

    for i, event in enumerate(events):
        title = event['title']
        current_desc = event['description'] or ''
        key = normalize_name(title)

        # Try each source
        found = False
        for source_name, source_data in sources.items():
            if key in source_data:
                source_event = source_data[key]
                new_desc = source_event.get('description') or source_event.get('content', '')

                # Only update if new description is better
                if new_desc and len(new_desc) > len(current_desc):
                    if not dry_run:
                        update_event_description(conn, event['id'], new_desc, source_name)

                    enriched += 1
                    found = True

                    if enriched <= 10 or enriched % 500 == 0:
                        try:
                            print(f"[{enriched}] {title}")
                            print(f"  From: {source_name}")
                            print(f"  Old: '{current_desc[:40]}' ({len(current_desc)} chars)")
                            print(f"  New: '{new_desc[:40]}' ({len(new_desc)} chars)")
                        except UnicodeEncodeError:
                            print(f"[{enriched}] (unicode title) - enriched")
                    break

        if not found:
            not_found += 1

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"Enriched: {enriched:,}")
    print(f"Not found: {not_found:,}")
    print(f"Success rate: {100*enriched/(enriched+not_found):.1f}%" if (enriched+not_found) > 0 else "N/A")

    if not dry_run and enriched > 0:
        print(f"\nNOTE: {enriched} events need re-embedding.")
        print("Run: python data/scripts/processing/embed_entities.py --target events --model small --yes")

    return enriched


def main():
    parser = argparse.ArgumentParser(description="Enrich Events from Collected Data")
    parser.add_argument(
        "--source",
        choices=["wikidata", "worldhistory", "all"],
        default="all",
        help="Data source to use"
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=50,
        help="Minimum description length to consider sufficient"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't update database"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Event Enrichment from Collected Data")
    print("=" * 60)

    # Load sources
    print("\nLoading sources...")
    sources = {}

    if args.source in ["wikidata", "all"]:
        sources["wikidata"] = load_wikidata_events()

    if args.source in ["worldhistory", "all"]:
        sources["worldhistory"] = load_worldhistory_events()

    if not sources:
        print("No sources loaded!")
        return

    # Connect and enrich
    conn = get_db_connection()
    print("Database connected!")

    try:
        enrich_events(conn, sources, args.min_length, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
