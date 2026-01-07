"""
Enrich locations table with coordinates from Pleiades dataset.

Pleiades is a gazetteer of ancient places (Mediterranean & Near East).
https://pleiades.stoa.org/

This script:
1. Loads Pleiades data
2. Builds name → coordinate lookup
3. Matches locations table entries
4. Updates coordinates where found
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

# Pleiades data path
PLEIADES_PATH = Path("C:/Projects/Chaldeas/data/external/pleiades-places.json")


def normalize_name(name: str) -> str:
    """Normalize a place name for matching."""
    if not name:
        return ""
    # Lowercase
    name = name.lower()
    # Remove diacritics (simple approach)
    name = name.replace('ā', 'a').replace('ē', 'e').replace('ī', 'i').replace('ō', 'o').replace('ū', 'u')
    # Remove punctuation and extra spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def build_pleiades_lookup(pleiades_data: dict) -> dict:
    """Build a name → (lat, lon, title, place_type) lookup from Pleiades data."""
    lookup = {}
    places = pleiades_data.get('@graph', [])

    for place in places:
        repr_point = place.get('reprPoint')
        if not repr_point:
            continue

        lon, lat = repr_point  # Pleiades uses [lon, lat]
        title = place.get('title', '')
        place_types = place.get('placeTypes', [])
        place_type = place_types[0] if place_types else None

        # Add title
        norm_title = normalize_name(title)
        if norm_title and norm_title not in lookup:
            lookup[norm_title] = (lat, lon, title, place_type)

        # Add all names
        for name_obj in place.get('names', []):
            for key in ['romanized', 'attested', 'nameTransliterated']:
                name = name_obj.get(key)
                if name:
                    norm_name = normalize_name(name)
                    if norm_name and norm_name not in lookup:
                        lookup[norm_name] = (lat, lon, title, place_type)

    return lookup


def main():
    print("=" * 60)
    print("CHALDEAS Location Enrichment - Pleiades")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Load Pleiades data
    print("[1/4] Loading Pleiades data...")
    if not PLEIADES_PATH.exists():
        print(f"ERROR: Pleiades file not found at {PLEIADES_PATH}")
        sys.exit(1)

    with open(PLEIADES_PATH, 'r', encoding='utf-8') as f:
        pleiades_data = json.load(f)

    total_places = len(pleiades_data.get('@graph', []))
    print(f"  -> Loaded {total_places:,} places")

    # Build lookup
    print("\n[2/4] Building name lookup...")
    lookup = build_pleiades_lookup(pleiades_data)
    print(f"  -> {len(lookup):,} unique name mappings")

    # Free memory
    del pleiades_data

    # Connect to database
    print("\n[3/4] Connecting to database...")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get locations without coordinates
    result = session.execute(text("""
        SELECT id, name, modern_name, type
        FROM locations
        WHERE latitude IS NULL OR longitude IS NULL
        ORDER BY name
    """))
    locations = list(result)
    print(f"  -> {len(locations):,} locations need coordinates")

    # Match and update
    print("\n[4/4] Matching locations...")
    matched = 0
    updated = 0
    match_log = []

    for loc_id, name, modern_name, loc_type in locations:
        # Try to match
        coord = None

        # Try original name
        norm_name = normalize_name(name)
        if norm_name in lookup:
            coord = lookup[norm_name]

        # Try modern name
        if not coord and modern_name:
            norm_modern = normalize_name(modern_name)
            if norm_modern in lookup:
                coord = lookup[norm_modern]

        # Try without common suffixes
        if not coord:
            for suffix in [' city', ' town', ' river', ' mountain', ' island']:
                test_name = norm_name.replace(suffix, '').strip()
                if test_name in lookup:
                    coord = lookup[test_name]
                    break

        if coord:
            lat, lon, pleiades_title, pleiades_type = coord
            matched += 1

            # Update database
            try:
                session.execute(text("""
                    UPDATE locations
                    SET latitude = :lat, longitude = :lon
                    WHERE id = :id AND (latitude IS NULL OR longitude IS NULL)
                """), {"lat": lat, "lon": lon, "id": loc_id})
                updated += 1

                if matched <= 20:
                    match_log.append(f"  {name} → {pleiades_title} ({lat:.4f}, {lon:.4f})")

            except Exception as e:
                session.rollback()
                print(f"  Error updating {name}: {e}")

        if matched % 1000 == 0 and matched > 0:
            session.commit()
            print(f"    {matched:,} matched, {updated:,} updated...")

    session.commit()

    # Summary
    print("\n" + "=" * 60)
    print("ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"Locations processed: {len(locations):,}")
    print(f"Matched in Pleiades: {matched:,} ({100*matched/len(locations):.1f}%)")
    print(f"Updated in DB: {updated:,}")
    print()

    # Show sample matches
    if match_log:
        print("Sample matches:")
        for log in match_log:
            print(log)

    # Final stats
    result = session.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(latitude) as with_coords
        FROM locations
    """))
    row = result.fetchone()
    print(f"\nFinal status:")
    print(f"  Total locations: {row[0]:,}")
    print(f"  With coordinates: {row[1]:,} ({100*row[1]/row[0]:.1f}%)")

    print(f"\nFinished: {datetime.now().isoformat()}")
    session.close()


if __name__ == "__main__":
    main()
