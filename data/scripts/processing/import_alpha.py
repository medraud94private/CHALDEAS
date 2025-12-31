#!/usr/bin/env python3
"""
Alpha Data Import Script

Imports structured data from raw collections into the database.
Phase A: Quick Wins - Already structured data

Usage:
    python data/scripts/processing/import_alpha.py --source pantheon
    python data/scripts/processing/import_alpha.py --source pleiades
    python data/scripts/processing/import_alpha.py --source all
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import unicodedata
from datetime import datetime

# Add backend to path
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
        # Construct from individual vars
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def slugify(text: str) -> str:
    """Create URL-safe slug from text."""
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text)
    # Convert to ASCII
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Lowercase and replace spaces/special chars
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text[:200]  # Limit length


def import_pantheon(conn) -> int:
    """
    Import historical figures from MIT Pantheon dataset.

    Pantheon has 59,902 historical figures with:
    - Name, birth/death years
    - Occupation/domain
    - Geographic origin
    - Notability metrics
    """
    print("\n" + "=" * 60)
    print("Importing Pantheon Historical Figures")
    print("=" * 60)

    pantheon_file = Path("data/raw/pantheon/pantheon_historical.json")
    if not pantheon_file.exists():
        print(f"Pantheon file not found: {pantheon_file}")
        return 0

    with open(pantheon_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} historical figures")

    # Prepare batch insert
    persons = []
    seen_slugs = set()

    for item in data:
        name = item.get('name', '').strip()
        if not name:
            continue

        # Create unique slug
        base_slug = slugify(name)
        if not base_slug:
            base_slug = f"person-{len(seen_slugs)}"
        slug = base_slug
        counter = 1
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        seen_slugs.add(slug)

        # Extract years (Pantheon format: birth_year, death_year)
        birth_year = item.get('birth_year')
        death_year = item.get('death_year')

        # Handle BCE conversion
        if birth_year is not None:
            try:
                birth_year = int(birth_year)
            except:
                birth_year = None

        if death_year is not None:
            try:
                death_year = int(death_year)
            except:
                death_year = None

        # Get occupation/category
        occupation = item.get('occupation', '')
        country = item.get('country', '')

        # Build biography from available info
        bio_parts = []
        if occupation:
            bio_parts.append(occupation.title())
        if country:
            bio_parts.append(f"From: {country}")

        biography = ". ".join(bio_parts) if bio_parts else None

        now = datetime.utcnow()
        persons.append((
            name,
            slug,
            birth_year,
            death_year,
            biography,
            now,  # created_at
            now,  # updated_at
        ))

    print(f"Prepared {len(persons)} persons for import")

    # Batch insert
    cur = conn.cursor()

    # Clear existing data (fresh import)
    cur.execute("DELETE FROM persons WHERE slug LIKE 'pantheon-%' OR biography LIKE '%Domain:%'")

    # Insert in batches
    batch_size = 1000
    inserted = 0

    for i in range(0, len(persons), batch_size):
        batch = persons[i:i+batch_size]

        try:
            execute_values(
                cur,
                """
                INSERT INTO persons (name, slug, birth_year, death_year, biography, created_at, updated_at)
                VALUES %s
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    birth_year = EXCLUDED.birth_year,
                    death_year = EXCLUDED.death_year,
                    biography = EXCLUDED.biography,
                    updated_at = EXCLUDED.updated_at
                """,
                batch,
                template="(%s, %s, %s, %s, %s, %s, %s)"
            )
            inserted += len(batch)
            print(f"  Inserted {inserted}/{len(persons)}...")
        except Exception as e:
            print(f"  Error in batch {i}: {e}")
            conn.rollback()
            continue

    conn.commit()
    print(f"Successfully imported {inserted} persons")
    return inserted


def import_pleiades(conn) -> int:
    """
    Import ancient places from Pleiades gazetteer.

    Pleiades has ~37,000 ancient places with:
    - Coordinates (lat/lng)
    - Ancient and modern names
    - Time periods
    """
    print("\n" + "=" * 60)
    print("Importing Pleiades Ancient Places")
    print("=" * 60)

    pleiades_file = Path("data/raw/pleiades/pleiades_locations.json")
    if not pleiades_file.exists():
        print(f"Pleiades file not found: {pleiades_file}")
        return 0

    with open(pleiades_file, 'r', encoding='utf-8') as f:
        places_data = json.load(f)

    print(f"Loaded {len(places_data)} places")

    locations = []

    for item in places_data:
        # Get name
        name = item.get('title', '')
        if not name:
            continue

        # Get coordinates from 'coordinates' field
        coords = item.get('coordinates')
        if not coords:
            continue

        # Support both formats: lat/lng and latitude/longitude
        lat = coords.get('lat') or coords.get('latitude')
        lng = coords.get('lng') or coords.get('longitude')

        if lat is None or lng is None:
            continue

        try:
            lat = float(lat)
            lng = float(lng)
        except:
            continue

        # Get type
        place_types = item.get('place_types', [])
        place_type = place_types[0] if place_types else 'unknown'

        # Get description
        description = item.get('description', '')

        # Get names (could have multiple)
        names = item.get('names', [])
        modern_name = None
        if names:
            # Look for modern names - names can be strings or dicts
            for n in names:
                name_str = n.get('name', n) if isinstance(n, dict) else n
                if isinstance(name_str, str) and 'modern' in name_str.lower():
                    modern_name = name_str
                    break

        now = datetime.utcnow()
        locations.append((
            name,
            lat,
            lng,
            place_type,
            modern_name,
            description[:1000] if description else None,
            now,  # created_at
            now,  # updated_at
        ))

    print(f"Prepared {len(locations)} locations with coordinates")

    cur = conn.cursor()

    # Insert in batches
    batch_size = 1000
    inserted = 0

    for i in range(0, len(locations), batch_size):
        batch = locations[i:i+batch_size]

        try:
            execute_values(
                cur,
                """
                INSERT INTO locations (name, latitude, longitude, type, modern_name, description, created_at, updated_at)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                batch,
                template="(%s, %s, %s, %s, %s, %s, %s, %s)"
            )
            inserted += len(batch)
            print(f"  Inserted {inserted}/{len(locations)}...")
        except Exception as e:
            print(f"  Error in batch {i}: {e}")
            conn.rollback()
            continue

    conn.commit()
    print(f"Successfully imported {inserted} locations")
    return inserted


def import_wikidata_events(conn) -> int:
    """
    Import events from Wikidata.
    """
    print("\n" + "=" * 60)
    print("Importing Wikidata Events")
    print("=" * 60)

    events_file = Path("data/raw/wikidata/wikidata_events.json")
    if not events_file.exists():
        print(f"Wikidata events file not found: {events_file}")
        return 0

    with open(events_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    events_data = data if isinstance(data, list) else data.get('events', data.get('data', []))
    print(f"Loaded {len(events_data)} events")

    events = []
    seen_slugs = set()

    for item in events_data:
        title = item.get('title') or item.get('name') or item.get('label', '')
        if not title:
            continue

        # Create unique slug
        base_slug = slugify(title)
        if not base_slug:
            continue
        slug = base_slug
        counter = 1
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        seen_slugs.add(slug)

        # Get year - support various date formats
        year = item.get('year') or item.get('date_start') or item.get('start_year') or item.get('date')
        if year is None:
            continue

        # Parse year from date string if needed (e.g., "1453-05-29")
        if isinstance(year, str):
            year_match = re.match(r'^(-?\d+)', year)
            if year_match:
                year = year_match.group(1)
            else:
                continue

        try:
            year = int(year)
        except:
            continue

        description = item.get('description', '')

        now = datetime.utcnow()
        events.append((
            title,
            slug,
            year,
            description[:2000] if description else None,
            3,  # default importance
            now,  # created_at
            now,  # updated_at
        ))

    print(f"Prepared {len(events)} events")

    cur = conn.cursor()

    # Insert
    batch_size = 500
    inserted = 0

    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]

        try:
            execute_values(
                cur,
                """
                INSERT INTO events (title, slug, date_start, description, importance, created_at, updated_at)
                VALUES %s
                ON CONFLICT (slug) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
                """,
                batch,
                template="(%s, %s, %s, %s, %s, %s, %s)"
            )
            inserted += len(batch)
        except Exception as e:
            print(f"  Error: {e}")
            conn.rollback()

    conn.commit()
    print(f"Successfully imported {inserted} events")
    return inserted


def import_all(conn):
    """Import all data sources."""
    total = 0

    total += import_pantheon(conn)
    total += import_pleiades(conn)
    total += import_wikidata_events(conn)

    print("\n" + "=" * 60)
    print(f"TOTAL IMPORTED: {total} records")
    print("=" * 60)

    return total


def main():
    parser = argparse.ArgumentParser(description="Alpha Data Importer")
    parser.add_argument(
        "--source",
        choices=["pantheon", "pleiades", "wikidata", "all"],
        default="all",
        help="Data source to import"
    )

    args = parser.parse_args()

    print("Alpha Data Import")
    print(f"Source: {args.source}")

    try:
        conn = get_db_connection()
        print("Database connected!")
    except Exception as e:
        print(f"Database connection failed: {e}")
        print("\nMake sure PostgreSQL is running and DATABASE_URL is set")
        return

    try:
        if args.source == "all":
            import_all(conn)
        elif args.source == "pantheon":
            import_pantheon(conn)
        elif args.source == "pleiades":
            import_pleiades(conn)
        elif args.source == "wikidata":
            import_wikidata_events(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
