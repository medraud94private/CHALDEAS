"""
Build unified gazetteer lookup table from multiple sources.

Sources:
- Pleiades (ancient places, CC BY)
- GeoNames (modern cities, CC BY)
- Natural Earth (major cities, Public Domain)

Creates a 'gazetteer' table for efficient place name → coordinate lookup.
"""

import os
import sys
import json
import re
import shapefile
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

DATA_DIR = Path("C:/Projects/Chaldeas/data/external")


def normalize_name(name: str) -> str:
    """Normalize place name for matching."""
    if not name:
        return ""
    name = name.lower()
    # Remove diacritics (simple)
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


def load_pleiades():
    """Load Pleiades data."""
    path = DATA_DIR / "pleiades-places.json"
    if not path.exists():
        print("  Pleiades file not found, skipping")
        return []

    print("  Loading Pleiades...")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = []
    for place in data.get('@graph', []):
        repr_point = place.get('reprPoint')
        if not repr_point:
            continue

        lon, lat = repr_point
        title = place.get('title', '')
        place_types = place.get('placeTypes', [])
        place_type = place_types[0] if place_types else None

        # Main title
        if title:
            records.append({
                'name': title,
                'name_normalized': normalize_name(title),
                'lat': lat,
                'lon': lon,
                'place_type': place_type,
                'source': 'pleiades',
                'population': None,
                'country': None,
            })

        # Alternative names
        for name_obj in place.get('names', []):
            for key in ['romanized', 'attested']:
                name = name_obj.get(key)
                if name and name != title:
                    records.append({
                        'name': name,
                        'name_normalized': normalize_name(name),
                        'lat': lat,
                        'lon': lon,
                        'place_type': place_type,
                        'source': 'pleiades',
                        'population': None,
                        'country': None,
                    })

    print(f"  -> {len(records):,} records from Pleiades")
    return records


def load_geonames(session, batch_size=10000):
    """Load GeoNames allCountries data directly to DB (streaming)."""
    # Try full file first, then fall back to cities15000
    path = DATA_DIR / "allCountries.txt"
    if not path.exists():
        path = DATA_DIR / "cities15000.txt"
    if not path.exists():
        print("  GeoNames file not found, skipping")
        return 0

    print(f"  Loading GeoNames from {path.name}...")

    count = 0
    batch = []
    seen_names = set()  # Track normalized names to avoid duplicates

    with open(path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parts = line.strip().split('\t')
            if len(parts) < 15:
                continue

            name = parts[1]
            ascii_name = parts[2]
            lat = float(parts[4])
            lon = float(parts[5])
            feature_code = parts[7]
            country = parts[8]
            try:
                population = int(parts[14]) if parts[14] else None
            except:
                population = None

            # Add main name
            norm = normalize_name(name)
            if norm and norm not in seen_names:
                seen_names.add(norm)
                batch.append({
                    'name': name[:500],
                    'name_normalized': norm[:500],
                    'lat': lat,
                    'lon': lon,
                    'place_type': feature_code,
                    'source': 'geonames',
                    'population': population,
                    'country': country,
                })

            # Add ASCII name if different
            if ascii_name and ascii_name != name:
                norm_ascii = normalize_name(ascii_name)
                if norm_ascii and norm_ascii not in seen_names:
                    seen_names.add(norm_ascii)
                    batch.append({
                        'name': ascii_name[:500],
                        'name_normalized': norm_ascii[:500],
                        'lat': lat,
                        'lon': lon,
                        'place_type': feature_code,
                        'source': 'geonames',
                        'population': population,
                        'country': country,
                    })

            # Commit in batches
            if len(batch) >= batch_size:
                session.execute(text("""
                    INSERT INTO gazetteer (name, name_normalized, latitude, longitude, place_type, source, population, country)
                    VALUES (:name, :name_normalized, :lat, :lon, :place_type, :source, :population, :country)
                    ON CONFLICT DO NOTHING
                """), batch)
                session.commit()
                count += len(batch)
                batch = []
                if count % 500000 == 0:
                    print(f"    {count:,} GeoNames records inserted...")

    # Insert remaining
    if batch:
        session.execute(text("""
            INSERT INTO gazetteer (name, name_normalized, latitude, longitude, place_type, source, population, country)
            VALUES (:name, :name_normalized, :lat, :lon, :place_type, :source, :population, :country)
            ON CONFLICT DO NOTHING
        """), batch)
        session.commit()
        count += len(batch)

    print(f"  -> {count:,} records from GeoNames")
    return count


def load_natural_earth():
    """Load Natural Earth populated places."""
    path = DATA_DIR / "natural_earth" / "ne_10m_populated_places"
    shp_path = str(path) + ".shp"
    if not Path(shp_path).exists():
        print("  Natural Earth file not found, skipping")
        return []

    print("  Loading Natural Earth...")
    records = []

    sf = shapefile.Reader(str(path))
    for i, (rec, shape) in enumerate(zip(sf.records(), sf.shapes())):
        name = rec['NAME']
        name_alt = rec['NAMEALT']
        country = rec['ADM0NAME']
        population = rec['POP_MAX']
        lon, lat = shape.points[0]

        records.append({
            'name': name,
            'name_normalized': normalize_name(name),
            'lat': lat,
            'lon': lon,
            'place_type': 'city',
            'source': 'naturalearth',
            'population': population,
            'country': country,
        })

        if name_alt and name_alt != name:
            records.append({
                'name': name_alt,
                'name_normalized': normalize_name(name_alt),
                'lat': lat,
                'lon': lon,
                'place_type': 'city',
                'source': 'naturalearth',
                'population': population,
                'country': country,
            })

    print(f"  -> {len(records):,} records from Natural Earth")
    return records


def main():
    print("=" * 60)
    print("CHALDEAS Gazetteer Builder")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Create database connection first
    print("[1/5] Connecting to database...")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create table
    print("\n[2/5] Creating gazetteer table...")
    session.execute(text("""
        DROP TABLE IF EXISTS gazetteer;
        CREATE TABLE gazetteer (
            id SERIAL PRIMARY KEY,
            name VARCHAR(500) NOT NULL,
            name_normalized VARCHAR(500) NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            place_type VARCHAR(100),
            source VARCHAR(50) NOT NULL,
            population BIGINT,
            country VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX idx_gazetteer_name_norm ON gazetteer(name_normalized);
        CREATE INDEX idx_gazetteer_source ON gazetteer(source);
    """))
    session.commit()
    print("  -> Table created")

    # Load Pleiades and Natural Earth (small, load to memory)
    print("\n[3/5] Loading Pleiades and Natural Earth...")
    pleiades_records = load_pleiades()
    natural_earth_records = load_natural_earth()

    # Insert Pleiades
    if pleiades_records:
        print("  Inserting Pleiades...")
        batch = []
        for rec in pleiades_records:
            batch.append(rec)
            if len(batch) >= 5000:
                session.execute(text("""
                    INSERT INTO gazetteer (name, name_normalized, latitude, longitude, place_type, source, population, country)
                    VALUES (:name, :name_normalized, :lat, :lon, :place_type, :source, :population, :country)
                    ON CONFLICT DO NOTHING
                """), batch)
                session.commit()
                batch = []
        if batch:
            session.execute(text("""
                INSERT INTO gazetteer (name, name_normalized, latitude, longitude, place_type, source, population, country)
                VALUES (:name, :name_normalized, :lat, :lon, :place_type, :source, :population, :country)
                ON CONFLICT DO NOTHING
            """), batch)
            session.commit()
        print(f"  -> {len(pleiades_records):,} Pleiades records inserted")

    # Insert Natural Earth
    if natural_earth_records:
        print("  Inserting Natural Earth...")
        batch = []
        for rec in natural_earth_records:
            batch.append(rec)
            if len(batch) >= 5000:
                session.execute(text("""
                    INSERT INTO gazetteer (name, name_normalized, latitude, longitude, place_type, source, population, country)
                    VALUES (:name, :name_normalized, :lat, :lon, :place_type, :source, :population, :country)
                    ON CONFLICT DO NOTHING
                """), batch)
                session.commit()
                batch = []
        if batch:
            session.execute(text("""
                INSERT INTO gazetteer (name, name_normalized, latitude, longitude, place_type, source, population, country)
                VALUES (:name, :name_normalized, :lat, :lon, :place_type, :source, :population, :country)
                ON CONFLICT DO NOTHING
            """), batch)
            session.commit()
        print(f"  -> {len(natural_earth_records):,} Natural Earth records inserted")

    # Load GeoNames (large, stream directly to DB)
    print("\n[4/5] Loading GeoNames (streaming)...")
    geonames_count = load_geonames(session, batch_size=10000)

    # Stats
    print("\n" + "=" * 60)
    print("[5/5] GAZETTEER BUILD COMPLETE")
    print("=" * 60)

    result = session.execute(text("""
        SELECT source, COUNT(*) FROM gazetteer GROUP BY source ORDER BY COUNT(*) DESC
    """))
    print("\nRecords by source:")
    for row in result:
        print(f"  {row[0]}: {row[1]:,}")

    total = session.execute(text("SELECT COUNT(*) FROM gazetteer")).scalar()
    print(f"\nTotal gazetteer entries: {total:,}")
    print(f"Finished: {datetime.now().isoformat()}")

    session.close()


if __name__ == "__main__":
    main()
