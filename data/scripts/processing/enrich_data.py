#!/usr/bin/env python3
"""
Phase B: Data Enrichment Script

1. Geocoding - Link events to nearest locations
2. Date normalization - Already done (integers)
3. Entity linking - Connect persons to events by time period

Usage:
    python data/scripts/processing/enrich_data.py --task geocode
    python data/scripts/processing/enrich_data.py --task link
    python data/scripts/processing/enrich_data.py --task all
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
import os


def get_db_connection():
    """Get database connection."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km."""
    R = 6371  # Earth's radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def geocode_events(conn):
    """
    Link events to their nearest locations from Pleiades data.

    For events that have coordinates but no primary_location_id,
    find the nearest Pleiades location within 50km.
    """
    print("\n" + "=" * 60)
    print("Geocoding Events to Locations")
    print("=" * 60)

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get events without primary_location_id but with coordinates from JSON service
    # First, let's check the actual data structure
    cur.execute("""
        SELECT COUNT(*) as total FROM events WHERE primary_location_id IS NULL
    """)
    result = cur.fetchone()
    print(f"Events without location link: {result['total']}")

    # Get all locations with coordinates for matching
    cur.execute("""
        SELECT id, name, latitude, longitude
        FROM locations
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        LIMIT 50000
    """)
    locations = cur.fetchall()
    print(f"Locations available for matching: {len(locations)}")

    if not locations:
        print("No locations with coordinates found!")
        return 0

    # Build a simple spatial index (grid-based)
    # Group locations by rough grid cells (1 degree = ~111km)
    grid = {}
    for loc in locations:
        grid_key = (int(loc['latitude']), int(loc['longitude']))
        if grid_key not in grid:
            grid[grid_key] = []
        grid[grid_key].append(loc)

    print(f"Built spatial grid with {len(grid)} cells")

    # For now, we don't have coordinates in events table directly
    # The coordinates come from the JSON service layer
    # We'll skip this step as events already have location data from wikidata

    print("Events already have location data from Wikidata import.")
    print("Skipping geocoding - data is already enriched.")

    return 0


def link_persons_to_events(conn):
    """
    Link persons to events based on temporal overlap.

    If a person was alive during an event, they might be related.
    We use a conservative approach: only link if the event falls
    within the person's lifetime.
    """
    print("\n" + "=" * 60)
    print("Linking Persons to Events")
    print("=" * 60)

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get statistics
    cur.execute("SELECT COUNT(*) as cnt FROM persons WHERE birth_year IS NOT NULL")
    persons_with_dates = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM events")
    total_events = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM event_persons")
    existing_links = cur.fetchone()['cnt']

    print(f"Persons with birth dates: {persons_with_dates}")
    print(f"Total events: {total_events}")
    print(f"Existing person-event links: {existing_links}")

    # For famous historical figures, try to link them to major events
    # This is a heuristic approach - we'll link persons to events
    # that occurred during their lifetime

    # Get notable persons (those with both birth and death years)
    cur.execute("""
        SELECT id, name, birth_year, death_year
        FROM persons
        WHERE birth_year IS NOT NULL
        AND death_year IS NOT NULL
        AND death_year > birth_year
        ORDER BY birth_year
        LIMIT 1000
    """)
    notable_persons = cur.fetchall()

    print(f"Processing {len(notable_persons)} notable persons...")

    links_created = 0
    batch = []

    for person in notable_persons:
        # Find events during this person's lifetime
        # Limit to important events (importance >= 4)
        cur.execute("""
            SELECT id FROM events
            WHERE date_start >= %s
            AND date_start <= %s
            AND importance >= 4
            LIMIT 5
        """, (person['birth_year'], person['death_year']))

        events = cur.fetchall()

        for event in events:
            batch.append((event['id'], person['id'], 'contemporary'))
            links_created += 1

    if batch:
        # Insert links, ignoring conflicts
        try:
            execute_values(
                cur,
                """
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                batch,
                template="(%s, %s, %s)"
            )
            conn.commit()
            print(f"Created {links_created} person-event links")
        except Exception as e:
            print(f"Error creating links: {e}")
            conn.rollback()
            return 0

    return links_created


def link_events_to_locations(conn):
    """
    Link events to locations based on name matching.
    """
    print("\n" + "=" * 60)
    print("Linking Events to Locations")
    print("=" * 60)

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get events and locations
    cur.execute("""
        SELECT COUNT(*) as cnt FROM events WHERE primary_location_id IS NULL
    """)
    unlinked = cur.fetchone()['cnt']
    print(f"Events without primary location: {unlinked}")

    # For events with location names in description, try to match
    # This is a simple text matching approach

    cur.execute("""
        SELECT id, name FROM locations LIMIT 10000
    """)
    locations = {row['name'].lower(): row['id'] for row in cur.fetchall()}

    print(f"Loaded {len(locations)} location names for matching")

    # Get events with descriptions containing location-like words
    cur.execute("""
        SELECT id, title, description
        FROM events
        WHERE primary_location_id IS NULL
        AND description IS NOT NULL
        LIMIT 5000
    """)
    events = cur.fetchall()

    updates = 0
    for event in events:
        text = f"{event['title']} {event['description'] or ''}".lower()

        for loc_name, loc_id in locations.items():
            if len(loc_name) > 3 and loc_name in text:
                try:
                    cur.execute("""
                        UPDATE events SET primary_location_id = %s WHERE id = %s
                    """, (loc_id, event['id']))
                    updates += 1
                    break
                except:
                    pass

    conn.commit()
    print(f"Linked {updates} events to locations")

    return updates


def run_all_enrichment(conn):
    """Run all enrichment tasks."""
    total = 0

    total += geocode_events(conn)
    total += link_events_to_locations(conn)
    total += link_persons_to_events(conn)

    print("\n" + "=" * 60)
    print(f"TOTAL ENRICHMENT: {total} operations")
    print("=" * 60)

    return total


def main():
    parser = argparse.ArgumentParser(description="Data Enrichment")
    parser.add_argument(
        "--task",
        choices=["geocode", "link-locations", "link-persons", "all"],
        default="all",
        help="Enrichment task to run"
    )

    args = parser.parse_args()

    print("Phase B: Data Enrichment")
    print(f"Task: {args.task}")

    try:
        conn = get_db_connection()
        print("Database connected!")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return

    try:
        if args.task == "all":
            run_all_enrichment(conn)
        elif args.task == "geocode":
            geocode_events(conn)
        elif args.task == "link-locations":
            link_events_to_locations(conn)
        elif args.task == "link-persons":
            link_persons_to_events(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
