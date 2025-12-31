#!/usr/bin/env python3
"""
Link Events to Persons by Name Matching

Searches for person names in event titles/descriptions.
"""

import sys
import os
import re
from pathlib import Path
from typing import Set, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def get_important_persons(conn, min_name_length: int = 5) -> Dict[str, int]:
    """Get persons with reasonably unique names."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get persons - prioritize those with longer, more unique names
    cur.execute("""
        SELECT id, name
        FROM persons
        WHERE LENGTH(name) >= %s
        AND name !~ '^[A-Z]\\.$'  -- Skip single initials
        AND name NOT IN ('The', 'King', 'Queen', 'Emperor', 'Pope')
        ORDER BY LENGTH(name) DESC
    """, (min_name_length,))

    persons = {}
    for row in cur.fetchall():
        name = row['name'].strip()
        # Skip very common names that would match too much
        if len(name.split()) >= 2 or len(name) >= 8:
            persons[name.lower()] = row['id']

    return persons


def get_events(conn) -> List[dict]:
    """Get all events with their text content."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, title, description
        FROM events
    """)
    return cur.fetchall()


def find_persons_in_text(text: str, persons: Dict[str, int]) -> Set[int]:
    """Find person IDs mentioned in text."""
    if not text:
        return set()

    text_lower = text.lower()
    found = set()

    for name, person_id in persons.items():
        # Use word boundary matching
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, text_lower):
            found.add(person_id)

    return found


def insert_event_person(conn, event_id: int, person_id: int, role: str = 'mentioned'):
    """Insert into event_persons junction table."""
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO event_persons (event_id, person_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (event_id, person_id, role))
    except Exception:
        pass


def main():
    print("=" * 60)
    print("Event-Person Linking (Name Matching)")
    print("=" * 60)

    conn = get_db_connection()
    print("Database connected!")

    # Get persons
    print("\nLoading persons...")
    persons = get_important_persons(conn)
    print(f"Persons for matching: {len(persons):,}")

    # Get events
    print("\nLoading events...")
    events = get_events(conn)
    print(f"Events: {len(events):,}")

    # Match
    print("\nMatching...")
    total_links = 0
    events_with_persons = 0

    for i, event in enumerate(events):
        text = f"{event['title']} {event['description'] or ''}"
        found_persons = find_persons_in_text(text, persons)

        if found_persons:
            events_with_persons += 1
            for person_id in found_persons:
                insert_event_person(conn, event['id'], person_id)
                total_links += 1

        if (i + 1) % 1000 == 0:
            conn.commit()
            print(f"  Processed {i+1}/{len(events)}... ({total_links} links found)")

    conn.commit()

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total links created: {total_links:,}")
    print(f"Events with persons: {events_with_persons:,}")
    print(f"Average persons per event: {total_links/max(events_with_persons,1):.1f}")

    conn.close()


if __name__ == "__main__":
    main()
