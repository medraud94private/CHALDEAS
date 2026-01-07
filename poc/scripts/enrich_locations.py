"""
Enrich locations table with coordinates from gazetteer.

Uses the unified gazetteer table (8.8M entries from Pleiades, GeoNames, Natural Earth)
to match locations and add coordinates.
"""

import os
import re
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)


def normalize_name(name: str) -> str:
    """Normalize place name for matching."""
    if not name:
        return ""
    name = name.lower()
    # Remove diacritics
    replacements = {
        'ā': 'a', 'ē': 'e', 'ī': 'i', 'ō': 'o', 'ū': 'u',
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
        'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
        'ñ': 'n', 'ç': 'c', 'ß': 'ss',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def main():
    print("=" * 60)
    print("CHALDEAS Location Enrichment via Gazetteer")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Connect to database
    print("[1/4] Connecting to database...")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check gazetteer size
    gaz_count = session.execute(text("SELECT COUNT(*) FROM gazetteer")).scalar()
    print(f"  Gazetteer entries: {gaz_count:,}")

    # Get locations needing coordinates
    print("\n[2/4] Finding locations without coordinates...")
    result = session.execute(text("""
        SELECT id, name, modern_name, type
        FROM locations
        WHERE latitude IS NULL OR longitude IS NULL
        ORDER BY name
    """))
    locations = list(result)
    print(f"  -> {len(locations):,} locations need coordinates")

    if len(locations) == 0:
        print("\n  All locations already have coordinates!")
        session.close()
        return

    # Match and update
    print("\n[3/4] Matching against gazetteer...")
    matched = 0
    updated = 0
    match_log = []

    for loc_id, name, modern_name, loc_type in locations:
        coord = None
        match_source = None

        # Try variations
        search_names = []
        if name:
            search_names.append(normalize_name(name))
        if modern_name:
            search_names.append(normalize_name(modern_name))

        # Try without common suffixes
        for n in list(search_names):
            for suffix in [' city', ' town', ' river', ' mountain', ' island', ' province', ' region']:
                stripped = n.replace(suffix, '').strip()
                if stripped and stripped not in search_names:
                    search_names.append(stripped)

        for search_name in search_names:
            if not search_name:
                continue

            # Query gazetteer (prefer high population and pleiades for ancient places)
            result = session.execute(text("""
                SELECT latitude, longitude, name, source, population
                FROM gazetteer
                WHERE name_normalized = :name
                ORDER BY
                    CASE source WHEN 'pleiades' THEN 1 WHEN 'naturalearth' THEN 2 ELSE 3 END,
                    population DESC NULLS LAST
                LIMIT 1
            """), {"name": search_name})
            row = result.fetchone()

            if row:
                coord = (row[0], row[1], row[2], row[3])
                match_source = search_name
                break

        if coord:
            lat, lon, gaz_name, source = coord
            matched += 1

            # Update database
            try:
                session.execute(text("""
                    UPDATE locations
                    SET latitude = :lat, longitude = :lon
                    WHERE id = :id AND (latitude IS NULL OR longitude IS NULL)
                """), {"lat": lat, "lon": lon, "id": loc_id})
                updated += 1

                if matched <= 30:
                    match_log.append(f"  {name} -> {gaz_name} ({lat:.4f}, {lon:.4f}) [{source}]")

            except Exception as e:
                session.rollback()
                print(f"  Error updating {name}: {e}")

        if matched % 1000 == 0 and matched > 0:
            session.commit()
            print(f"    {matched:,} matched, {updated:,} updated...")

    session.commit()

    # Summary
    print("\n" + "=" * 60)
    print("[4/4] ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"Locations processed: {len(locations):,}")
    if len(locations) > 0:
        print(f"Matched in gazetteer: {matched:,} ({100*matched/len(locations):.1f}%)")
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
