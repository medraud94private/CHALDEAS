#!/usr/bin/env python3
"""Update events with coordinates directly from wikidata."""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

WIKIDATA_FILE = Path(__file__).parent.parent.parent / "raw" / "wikidata" / "wikidata_events.json"

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)

def main():
    print("=" * 60)
    print("Update Events with Wikidata Coordinates")
    print("=" * 60)

    # Load wikidata
    with open(WIKIDATA_FILE, 'r', encoding='utf-8') as f:
        wikidata = json.load(f)

    # Index by normalized name
    coords_by_name = {}
    for e in wikidata:
        if not e:
            continue
        coords = e.get('coordinates', {})
        if coords and coords.get('latitude') and coords.get('longitude'):
            name = e.get('name', '').strip().lower()
            if name and not name.startswith('q'):
                coords_by_name[name] = {
                    'lat': coords['latitude'],
                    'lng': coords['longitude']
                }

    print(f"Wikidata events with coords: {len(coords_by_name):,}")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print("Database connected!")

    # Get events without location
    cur.execute("""
        SELECT id, title FROM events WHERE primary_location_id IS NULL
    """)
    events = cur.fetchall()
    print(f"Events without location: {len(events):,}")

    # Get locations
    cur.execute("""
        SELECT id, name, latitude, longitude FROM locations
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    locations = cur.fetchall()

    # Index locations by approx coords
    loc_by_coords = {}
    for loc in locations:
        key = (round(float(loc['latitude']), 1), round(float(loc['longitude']), 1))
        if key not in loc_by_coords:
            loc_by_coords[key] = loc['id']

    print(f"Locations indexed: {len(loc_by_coords):,}")

    updated = 0
    for event in events:
        title_lower = event['title'].strip().lower()
        coords = coords_by_name.get(title_lower)

        if coords:
            # Find nearest location
            key = (round(coords['lat'], 1), round(coords['lng'], 1))
            loc_id = loc_by_coords.get(key)

            if loc_id:
                try:
                    cur.execute("""
                        UPDATE events SET primary_location_id = %s WHERE id = %s
                    """, (loc_id, event['id']))
                    updated += 1
                except:
                    conn.rollback()

        if updated > 0 and updated % 500 == 0:
            conn.commit()
            print(f"  Updated: {updated:,}")

    conn.commit()
    print()
    print("=" * 60)
    print(f"Total updated: {updated:,}")
    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    main()
