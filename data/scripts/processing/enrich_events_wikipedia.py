#!/usr/bin/env python3
"""
Enrich Events with Wikipedia Descriptions

Fetches Wikipedia summaries for events with missing or short descriptions.

Usage:
    python data/scripts/processing/enrich_events_wikipedia.py --limit 100
    python data/scripts/processing/enrich_events_wikipedia.py --min-length 50
    python data/scripts/processing/enrich_events_wikipedia.py --all
"""

import argparse
import sys
import os
import time
import re
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
import requests

# Wikipedia API endpoint
WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

# Rate limiting
REQUEST_DELAY = 0.1  # seconds between requests


def get_db_connection():
    """Get database connection."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def clean_title_for_search(title: str) -> str:
    """Clean event title for Wikipedia search."""
    # Remove common prefixes/suffixes
    cleaned = title

    # Remove year prefixes like "1945 " or "(1945)"
    cleaned = re.sub(r'^\d{4}\s+', '', cleaned)
    cleaned = re.sub(r'\s*\(\d{4}\)$', '', cleaned)

    # Remove "Battle of the" -> "Battle of"
    # Keep "Battle of X" as is, good for Wikipedia

    return cleaned.strip()


def search_wikipedia(query: str) -> Optional[str]:
    """
    Search Wikipedia and return the best matching page title.
    """
    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 3,
        "format": "json"
    }

    try:
        response = requests.get(
            search_url,
            params=params,
            headers={"User-Agent": "CHALDEAS/1.0 (Historical Knowledge System)"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("query", {}).get("search", [])
            if results:
                # Return the first result's title
                return results[0].get("title")

    except Exception:
        pass

    return None


def fetch_wikipedia_summary(title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch Wikipedia summary for a given title.

    Returns:
        Tuple of (summary, wikipedia_url) or (None, None) if not found
    """
    headers = {"User-Agent": "CHALDEAS/1.0 (Historical Knowledge System)"}

    def try_fetch(search_title: str) -> Tuple[Optional[str], Optional[str]]:
        encoded = urllib.parse.quote(search_title.replace(' ', '_'))
        try:
            response = requests.get(f"{WIKI_API}{encoded}", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "standard":
                    summary = data.get("extract", "")
                    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                    if summary and len(summary) > 50:
                        return summary, url
        except Exception:
            pass
        return None, None

    # 1. Try exact title
    result = try_fetch(title)
    if result[0]:
        return result

    # 2. Try cleaned title
    cleaned = clean_title_for_search(title)
    if cleaned != title:
        result = try_fetch(cleaned)
        if result[0]:
            return result

    # 3. Try Wikipedia search API
    search_result = search_wikipedia(title)
    if search_result and search_result.lower() != title.lower():
        result = try_fetch(search_result)
        if result[0]:
            return result

    return None, None


def get_events_to_enrich(conn, min_length: int = 50, limit: Optional[int] = None):
    """Get events that need enrichment."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT id, title, description, wikipedia_url
        FROM events
        WHERE description IS NULL
           OR description = ''
           OR LENGTH(description) < %s
        ORDER BY
            CASE WHEN description IS NULL OR description = '' THEN 0 ELSE 1 END,
            LENGTH(COALESCE(description, ''))
    """

    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query, (min_length,))
    return cur.fetchall()


def update_event(conn, event_id: int, description: str, wikipedia_url: str):
    """Update event with new description and clear embedding for re-embedding."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE events
        SET description = %s,
            wikipedia_url = %s,
            embedding = NULL,
            updated_at = NOW()
        WHERE id = %s
    """, (description, wikipedia_url, event_id))
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Enrich Events with Wikipedia")
    parser.add_argument(
        "--min-length",
        type=int,
        default=50,
        help="Minimum description length to consider 'good enough' (default: 50)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of events to process"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all events needing enrichment (no limit)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't update database, just show what would be done"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Event Enrichment via Wikipedia")
    print("=" * 60)
    print(f"Min description length: {args.min_length}")

    conn = get_db_connection()
    print("Database connected!")

    # Get events to enrich
    limit = None if args.all else (args.limit or 100)
    events = get_events_to_enrich(conn, args.min_length, limit)

    print(f"Events to enrich: {len(events)}")
    print()

    if not events:
        print("No events need enrichment!")
        conn.close()
        return

    # Process events
    enriched = 0
    failed = 0

    for i, event in enumerate(events):
        title = event['title']
        current_desc = event['description'] or ''

        try:
            print(f"[{i+1}/{len(events)}] {title}")
            print(f"  Current: {current_desc[:50]}..." if len(current_desc) > 50 else f"  Current: '{current_desc}'")
        except UnicodeEncodeError:
            print(f"[{i+1}/{len(events)}] (processing...)")

        # Fetch from Wikipedia
        summary, wiki_url = fetch_wikipedia_summary(title)

        if summary:
            try:
                print(f"  Found: {summary[:60]}...")
            except UnicodeEncodeError:
                print(f"  Found: (wiki summary)")

            if not args.dry_run:
                update_event(conn, event['id'], summary, wiki_url)

            enriched += 1
        else:
            print(f"  Not found on Wikipedia")
            failed += 1

        # Rate limiting
        time.sleep(REQUEST_DELAY)

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Enriched: {enriched}")
    print(f"Not found: {failed}")
    print(f"Success rate: {100*enriched/(enriched+failed):.1f}%")

    if not args.dry_run and enriched > 0:
        print()
        print(f"NOTE: {enriched} events had their embeddings cleared.")
        print("Run embed_entities.py to re-embed them:")
        print("  python data/scripts/processing/embed_entities.py --target events --model small --yes")

    conn.close()


if __name__ == "__main__":
    main()
