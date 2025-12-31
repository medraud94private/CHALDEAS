#!/usr/bin/env python3
"""
Import Diverse Events from Wikidata

Imports political, natural, and other non-battle events from collected wikidata.

Usage:
    python data/scripts/processing/import_diverse_events.py --categories political natural
    python data/scripts/processing/import_diverse_events.py --all
"""

import argparse
import sys
import os
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

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


def ensure_category(conn, category_name: str) -> int:
    """Ensure category exists and return its ID."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check if exists
    cur.execute("SELECT id FROM categories WHERE slug = %s", (category_name,))
    result = cur.fetchone()

    if result:
        return result['id']

    # Create category
    cur.execute("""
        INSERT INTO categories (name, slug, created_at, updated_at)
        VALUES (%s, %s, NOW(), NOW())
        RETURNING id
    """, (category_name.title(), category_name))
    conn.commit()
    return cur.fetchone()['id']


def parse_date(date_str: Optional[str]) -> Optional[int]:
    """Parse date string to year integer."""
    if not date_str:
        return None

    # Handle various formats
    try:
        # ISO format: 1945-05-08
        if '-' in str(date_str):
            year = int(str(date_str).split('-')[0])
            return year
        # Just year
        return int(date_str)
    except (ValueError, TypeError):
        return None


def get_existing_titles(conn) -> set:
    """Get set of existing event titles."""
    cur = conn.cursor()
    cur.execute("SELECT LOWER(title) FROM events")
    return {row[0] for row in cur.fetchall()}


def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title."""
    import re
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:100]


def import_events(conn, events: List[dict], category_id: int, existing_titles: set) -> int:
    """Import events to database."""
    cur = conn.cursor()
    imported = 0

    for event in events:
        title = event.get('name', '').strip()
        if not title:
            continue

        # Skip if exists
        if title.lower() in existing_titles:
            continue

        description = event.get('description', '')
        date_start = parse_date(event.get('date'))
        slug = generate_slug(title)

        # Get coordinates if available
        coords = event.get('coordinates', {})
        lat = coords.get('latitude') if coords else None
        lng = coords.get('longitude') if coords else None

        try:
            cur.execute("""
                INSERT INTO events (title, slug, description, date_start, category_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """, (title, slug, description, date_start, category_id))
            imported += 1
            existing_titles.add(title.lower())
        except Exception as e:
            conn.rollback()
            continue

    conn.commit()
    return imported


def main():
    parser = argparse.ArgumentParser(description="Import Diverse Events")
    parser.add_argument(
        "--categories",
        nargs='+',
        default=['political', 'natural'],
        help="Categories to import (political, natural, etc.)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit events per category"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Import Diverse Events from Wikidata")
    print("=" * 60)

    # Load wikidata events
    wikidata_path = DATA_DIR / "wikidata" / "wikidata_events.json"
    with open(wikidata_path, 'r', encoding='utf-8') as f:
        all_events = json.load(f)

    print(f"Loaded {len(all_events):,} events from wikidata")

    # Connect to DB
    conn = get_db_connection()
    print("Database connected!")

    # Get existing titles
    existing_titles = get_existing_titles(conn)
    print(f"Existing events: {len(existing_titles):,}")

    total_imported = 0

    for category in args.categories:
        print(f"\n--- Importing {category} events ---")

        # Filter events by category and valid names (not Q-IDs)
        category_events = [
            e for e in all_events
            if e.get('category') == category
            and e.get('name', '').strip()
            and not e.get('name', '').startswith('Q')  # Skip Q-IDs
        ]
        print(f"Found {len(category_events):,} {category} events in wikidata")

        if args.limit:
            category_events = category_events[:args.limit]

        # Ensure category exists
        category_id = ensure_category(conn, category)

        # Import
        imported = import_events(conn, category_events, category_id, existing_titles)
        print(f"Imported: {imported:,}")
        total_imported += imported

    print(f"\n{'=' * 60}")
    print(f"TOTAL IMPORTED: {total_imported:,}")
    print("=" * 60)

    if total_imported > 0:
        print("\nNOTE: Run embedding for new events:")
        print("  python data/scripts/processing/embed_entities.py --target events --model small --yes")

    conn.close()


if __name__ == "__main__":
    main()
