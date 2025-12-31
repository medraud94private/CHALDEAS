#!/usr/bin/env python3
"""
Link Events to Locations by Coordinates

Matches events to nearest locations using coordinate proximity.

Usage:
    python data/scripts/processing/link_events_locations.py
    python data/scripts/processing/link_events_locations.py --max-distance 10  # km
    python data/scripts/processing/link_events_locations.py --dry-run
"""

import argparse
import sys
import os
import json
import math
from pathlib import Path
from typing import Optional, Tuple, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

DATA_DIR = Path(__file__).parent.parent.parent / "raw"


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def load_wikidata_events_with_coords() -> dict:
    """Load wikidata events that have coordinates, indexed by name."""
    wikidata_path = DATA_DIR / "wikidata" / "wikidata_events.json"

    with open(wikidata_path, 'r', encoding='utf-8') as f:
        events = json.load(f)

    # Index by normalized name
    indexed = {}
    for event in events:
        coords = event.get('coordinates', {})
        if coords and coords.get('latitude') and coords.get('longitude'):
            name = event.get('name', '').strip().lower()
            if name and not name.startswith('q'):
                indexed[name] = {
                    'lat': coords['latitude'],
                    'lng': coords['longitude'],
                    'wikidata_id': event.get('wikidata_id')
                }

    return indexed


def get_all_locations(conn) -> List[dict]:
    """Get all locations with coordinates."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, name, latitude, longitude
        FROM locations
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    # Convert Decimal to float
    locations = []
    for row in cur.fetchall():
        locations.append({
            'id': row['id'],
            'name': row['name'],
            'latitude': float(row['latitude']),
            'longitude': float(row['longitude'])
        })
    return locations


def find_nearest_location(
    event_lat: float,
    event_lng: float,
    locations: List[dict],
    max_distance: float = 50.0
) -> Optional[Tuple[int, str, float]]:
    """Find nearest location to event coordinates."""
    nearest = None
    min_distance = float('inf')

    for loc in locations:
        dist = haversine_distance(
            event_lat, event_lng,
            loc['latitude'], loc['longitude']
        )

        if dist < min_distance and dist <= max_distance:
            min_distance = dist
            nearest = (loc['id'], loc['name'], dist)

    return nearest


def get_events_without_location(conn) -> List[dict]:
    """Get events that don't have a primary_location_id set."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, title
        FROM events
        WHERE primary_location_id IS NULL
    """)
    return cur.fetchall()


def update_event_location(conn, event_id: int, location_id: int):
    """Update event's primary_location_id."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE events
        SET primary_location_id = %s, updated_at = NOW()
        WHERE id = %s
    """, (location_id, event_id))


def insert_event_location(conn, event_id: int, location_id: int):
    """Insert into event_locations junction table."""
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO event_locations (event_id, location_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (event_id, location_id))
    except Exception:
        pass  # Table might not exist or other issue


def main():
    parser = argparse.ArgumentParser(description="Link Events to Locations")
    parser.add_argument(
        "--max-distance",
        type=float,
        default=50.0,
        help="Maximum distance in km to consider a match (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't update database"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Event-Location Linking (Coordinate-based)")
    print("=" * 60)
    print(f"Max distance: {args.max_distance} km")

    # Load wikidata coordinates
    print("\nLoading wikidata event coordinates...")
    wikidata_coords = load_wikidata_events_with_coords()
    print(f"Events with coordinates: {len(wikidata_coords):,}")

    # Connect to DB
    conn = get_db_connection()
    print("Database connected!")

    # Get all locations
    print("\nLoading locations from DB...")
    locations = get_all_locations(conn)
    print(f"Locations: {len(locations):,}")

    # Get events without location
    print("\nFinding events without location...")
    events = get_events_without_location(conn)
    print(f"Events to process: {len(events):,}")

    # Match events to locations
    linked = 0
    not_found_coords = 0
    not_found_location = 0

    for i, event in enumerate(events):
        title = event['title']
        title_lower = title.strip().lower()

        # Get coordinates from wikidata
        coords = wikidata_coords.get(title_lower)

        if not coords:
            not_found_coords += 1
            continue

        # Find nearest location
        nearest = find_nearest_location(
            coords['lat'], coords['lng'],
            locations,
            args.max_distance
        )

        if nearest:
            loc_id, loc_name, distance = nearest

            if not args.dry_run:
                update_event_location(conn, event['id'], loc_id)
                insert_event_location(conn, event['id'], loc_id)
                conn.commit()

            linked += 1

            if linked <= 10 or linked % 1000 == 0:
                try:
                    print(f"[{linked}] {title} -> {loc_name} ({distance:.1f} km)")
                except UnicodeEncodeError:
                    print(f"[{linked}] (linked)")
        else:
            not_found_location += 1

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Linked: {linked:,}")
    print(f"No coordinates in wikidata: {not_found_coords:,}")
    print(f"No location within {args.max_distance}km: {not_found_location:,}")

    if linked > 0:
        print(f"\nSuccess rate: {100*linked/len(events):.1f}%")

    conn.close()


if __name__ == "__main__":
    main()
