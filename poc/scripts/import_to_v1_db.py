#!/usr/bin/env python3
"""
Import aggregated NER data into V1 PostgreSQL database.

This script imports:
1. Seed periods (from backend/app/db/seeds/periods.json)
2. Aggregated NER data (from poc/data/integrated_ner_full/aggregated/)
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import hashlib

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from name."""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:255]


def import_seed_periods(session):
    """Import hierarchical periods from seed file."""
    seed_path = Path(__file__).parent.parent.parent / "backend/app/db/seeds/periods.json"

    if not seed_path.exists():
        print(f"  Seed file not found: {seed_path}")
        return 0

    with open(seed_path, encoding='utf-8') as f:
        data = json.load(f)

    count = 0

    def insert_period(period_data: dict, parent_id: Optional[int] = None) -> int:
        nonlocal count

        # Check if exists
        result = session.execute(
            text("SELECT id FROM periods WHERE slug = :slug"),
            {"slug": period_data["slug"]}
        ).fetchone()

        if result:
            period_id = result[0]
        else:
            # Insert new period (matching actual schema)
            result = session.execute(
                text("""
                    INSERT INTO periods (name, name_ko, slug, year_start, year_end,
                                        scale, description, description_ko,
                                        parent_id, is_manual, created_at, updated_at)
                    VALUES (:name, :name_ko, :slug, :year_start, :year_end,
                            :scale, :description, :description_ko,
                            :parent_id, :is_manual, NOW(), NOW())
                    RETURNING id
                """),
                {
                    "name": period_data["name"],
                    "name_ko": period_data.get("name_ko"),
                    "slug": period_data["slug"],
                    "year_start": period_data.get("year_start"),
                    "year_end": period_data.get("year_end"),
                    "scale": period_data.get("scale", "conjuncture"),
                    "description": period_data.get("description"),
                    "description_ko": period_data.get("description_ko"),
                    "parent_id": parent_id,
                    "is_manual": period_data.get("is_manual", False)
                }
            )
            period_id = result.fetchone()[0]
            count += 1
            print(f"    + {period_data['name']}")

        # Process children
        for child in period_data.get("children", []):
            insert_period(child, period_id)

        return period_id

    for period in data.get("periods", []):
        insert_period(period)

    session.commit()
    return count


def import_aggregated_periods(session, data_path: Path):
    """Import NER-extracted periods."""
    periods_file = data_path / "periods.json"
    if not periods_file.exists():
        return 0

    with open(periods_file, encoding='utf-8') as f:
        periods = json.load(f)

    count = 0
    batch_size = 1000

    for i in range(0, len(periods), batch_size):
        batch = periods[i:i+batch_size]
        for period in batch:
            slug = generate_slug(period["name"])

            # Skip if exists
            exists = session.execute(
                text("SELECT 1 FROM periods WHERE slug = :slug"),
                {"slug": slug}
            ).fetchone()

            if exists:
                continue

            try:
                session.execute(
                    text("""
                        INSERT INTO periods (name, slug, year_start, year_end,
                                            scale, is_manual, created_at, updated_at)
                        VALUES (:name, :slug, :year_start, :year_end,
                                'conjuncture', false, NOW(), NOW())
                    """),
                    {
                        "name": period["name"][:255],
                        "slug": slug,
                        "year_start": period.get("start_year"),
                        "year_end": period.get("end_year")
                    }
                )
                count += 1
            except Exception:
                session.rollback()
                continue  # Skip duplicates

        session.commit()
        if (i + batch_size) % 5000 == 0:
            print(f"    Periods: {i + batch_size:,} processed...")

    return count


def import_polities(session, data_path: Path):
    """Import NER-extracted polities."""
    polities_file = data_path / "polities.json"
    if not polities_file.exists():
        return 0

    with open(polities_file, encoding='utf-8') as f:
        polities = json.load(f)

    count = 0
    batch_size = 1000

    for i in range(0, len(polities), batch_size):
        batch = polities[i:i+batch_size]
        for polity in batch:
            slug = generate_slug(polity["name"])

            # Skip if exists
            exists = session.execute(
                text("SELECT 1 FROM polities WHERE slug = :slug"),
                {"slug": slug}
            ).fetchone()

            if exists:
                continue

            confidence = polity.get("confidence", 0.5)
            try:
                session.execute(
                    text("""
                        INSERT INTO polities (name, slug, polity_type, start_year, end_year,
                                             avg_confidence, certainty, created_at, updated_at)
                        VALUES (:name, :slug, :polity_type, :start_year, :end_year,
                                :confidence, :certainty, NOW(), NOW())
                    """),
                    {
                        "name": polity["name"][:255],
                        "slug": slug,
                        "polity_type": (polity.get("polity_type") or "unknown")[:50],
                        "start_year": polity.get("start_year"),
                        "end_year": polity.get("end_year"),
                        "confidence": confidence,
                        "certainty": "fact" if confidence >= 0.9 else "probable" if confidence >= 0.7 else "legendary"
                    }
                )
                count += 1
            except Exception:
                session.rollback()
                continue

        session.commit()
        if (i + batch_size) % 10000 == 0:
            print(f"    Polities: {i + batch_size:,} processed...")

    return count


def import_persons(session, data_path: Path):
    """Import NER-extracted persons."""
    persons_file = data_path / "persons.json"
    if not persons_file.exists():
        return 0

    with open(persons_file, encoding='utf-8') as f:
        persons = json.load(f)

    count = 0
    batch_size = 1000

    for i in range(0, len(persons), batch_size):
        batch = persons[i:i+batch_size]
        for person in batch:
            slug = generate_slug(person["name"])

            # Use certainty based on confidence
            confidence = person.get("confidence", 0.5)
            if confidence >= 0.9:
                certainty = "fact"
            elif confidence >= 0.7:
                certainty = "probable"
            elif confidence >= 0.4:
                certainty = "legendary"
            else:
                certainty = "mythological"

            # Skip if exists
            exists = session.execute(
                text("SELECT 1 FROM persons WHERE slug = :slug"),
                {"slug": slug}
            ).fetchone()

            if exists:
                continue

            try:
                session.execute(
                    text("""
                        INSERT INTO persons (name, slug, birth_year, death_year, role, era,
                                            certainty, mention_count, avg_confidence,
                                            created_at, updated_at)
                        VALUES (:name, :slug, :birth_year, :death_year, :role, :era,
                                :certainty, :mention_count, :confidence, NOW(), NOW())
                    """),
                    {
                        "name": person["name"][:500],
                        "slug": slug,
                        "birth_year": person.get("birth_year"),
                        "death_year": person.get("death_year"),
                        "role": (person.get("role") or "")[:255],
                        "era": (person.get("era") or "")[:100],
                        "certainty": certainty,
                        "mention_count": person.get("mention_count", 1),
                        "confidence": confidence
                    }
                )
                count += 1
            except Exception:
                session.rollback()
                continue

        session.commit()
        if (i + batch_size) % 10000 == 0:
            print(f"    Persons: {i + batch_size:,} processed...")

    return count


def import_locations(session, data_path: Path):
    """Import NER-extracted locations."""
    # Prefer enriched version if available
    locations_file = data_path / "locations_enriched.json"
    if not locations_file.exists():
        locations_file = data_path / "locations.json"
    if not locations_file.exists():
        return 0

    with open(locations_file, encoding='utf-8') as f:
        locations = json.load(f)

    count = 0
    batch_size = 1000

    for i in range(0, len(locations), batch_size):
        batch = locations[i:i+batch_size]
        for loc in batch:
            name = loc["name"][:255]
            loc_type = loc.get("location_type", "unknown")

            # Skip if exists (by name since no slug)
            exists = session.execute(
                text("SELECT 1 FROM locations WHERE name = :name"),
                {"name": name}
            ).fetchone()

            if exists:
                continue

            try:
                session.execute(
                    text("""
                        INSERT INTO locations (name, type, latitude, longitude,
                                              modern_name, created_at, updated_at)
                        VALUES (:name, :type, :lat, :lon, :modern_name, NOW(), NOW())
                    """),
                    {
                        "name": name,
                        "type": loc_type[:50] if loc_type else None,
                        "lat": loc.get("latitude"),
                        "lon": loc.get("longitude"),
                        "modern_name": loc.get("modern_name", "")[:255] if loc.get("modern_name") else None
                    }
                )
                count += 1
            except Exception:
                session.rollback()
                continue

        session.commit()
        if (i + batch_size) % 10000 == 0:
            print(f"    Locations: {i + batch_size:,} processed...")

    return count


def import_events(session, data_path: Path, force_all: bool = False):
    """Import NER-extracted events.

    Args:
        force_all: If True, import all events with unique slugs (add suffix if needed)
    """
    events_file = data_path / "events.json"
    if not events_file.exists():
        return 0

    with open(events_file, encoding='utf-8') as f:
        events = json.load(f)

    count = 0
    skipped = 0
    batch_size = 1000

    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        for idx, event in enumerate(batch):
            base_slug = generate_slug(event["name"])
            title = event["name"][:500]

            # source_docs 정보 추출 (첫 번째 소스)
            source_docs = event.get("source_docs", [])
            first_source = source_docs[0] if source_docs else None
            mention_count = event.get("mention_count", 1)

            if force_all:
                # 고유 slug 생성 (ner-{base}-{index})
                slug = f"ner-{base_slug}-{i+idx:06d}"[:255]
            else:
                slug = base_slug
                # Skip if exists
                exists = session.execute(
                    text("SELECT 1 FROM events WHERE slug = :slug"),
                    {"slug": slug}
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

            # Determine certainty
            confidence = event.get("confidence", 0.5)
            if confidence >= 0.9:
                certainty = "fact"
            elif confidence >= 0.7:
                certainty = "probable"
            elif confidence >= 0.4:
                certainty = "legendary"
            else:
                certainty = "mythological"

            # Note: description is left NULL for NER-extracted events
            # Real descriptions should be enriched later from Wikipedia or other sources

            try:
                # Use savepoint to prevent batch-wide rollback on individual failure
                with session.begin_nested():
                    session.execute(
                        text("""
                            INSERT INTO events (title, slug, date_start, certainty,
                                               temporal_scale, description, created_at, updated_at)
                            VALUES (:title, :slug, :year, :certainty,
                                    'evenementielle', NULL, NOW(), NOW())
                        """),
                        {
                            "title": title[:500],  # Ensure truncation
                            "slug": slug,
                            "year": event.get("year"),
                            "certainty": certainty
                        }
                    )
                count += 1
            except Exception as e:
                # Savepoint automatically rolled back, continue with next event
                continue

        session.commit()
        if (i + batch_size) % 10000 == 0:
            print(f"    Events: {i + batch_size:,} processed... (imported: {count:,}, skipped: {skipped:,})")

    if skipped > 0:
        print(f"    [INFO] {skipped:,} events skipped (slug exists). Use --force-all to import all.")

    return count


def create_import_batch(session, description: str) -> int:
    """Create an import batch record."""
    result = session.execute(
        text("""
            INSERT INTO import_batches (batch_name, batch_type, status,
                                       started_at, created_at, updated_at)
            VALUES (:name, 'aggregated_ner', 'processing', NOW(), NOW(), NOW())
            RETURNING id
        """),
        {"name": description}
    )
    batch_id = result.fetchone()[0]
    session.commit()
    return batch_id


def update_import_batch(session, batch_id: int, total: int, success: int, failed: int):
    """Update import batch status."""
    session.execute(
        text("""
            UPDATE import_batches
            SET status = 'completed',
                total_entities = :total,
                new_entities = :success,
                failed_documents = :failed,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = :batch_id
        """),
        {"batch_id": batch_id, "total": total, "success": success, "failed": failed}
    )
    session.commit()


def main():
    """Main import process."""
    import argparse
    parser = argparse.ArgumentParser(description='Import NER data to V1 database')
    parser.add_argument('--force-all', action='store_true',
                        help='Import all events with unique slugs (even if name exists)')
    parser.add_argument('--events-only', action='store_true',
                        help='Only import events (skip periods, polities, persons, locations)')
    args = parser.parse_args()

    print("=" * 60)
    print("CHALDEAS V1 Database Import")
    print("=" * 60)
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"Started: {datetime.now().isoformat()}")
    if args.force_all:
        print("Mode: FORCE ALL (import all events with unique slugs)")
    print()

    session = Session()

    try:
        # Create import batch record
        batch_id = create_import_batch(session, f"NER Import {datetime.now().strftime('%Y%m%d_%H%M%S')}")
        print(f"Import Batch ID: {batch_id}")
        print()

        total_imported = 0

        # Data path
        data_path = Path(__file__).parent.parent / "data/integrated_ner_full/aggregated"

        if not data_path.exists():
            print(f"\nAggregated data not found at: {data_path}")
            print("Run aggregate_ner_results.py first.")
            return

        if args.events_only:
            # Events only mode - skip other entities
            print("[Events Only Mode] Skipping periods, polities, persons, locations...")
            print("\n[1/1] Importing events...")
            count = import_events(session, data_path, force_all=args.force_all)
            print(f"  -> {count} events imported")
            total_imported += count
        else:
            # Full import mode
            # 1. Import seed periods
            print("[1/6] Importing seed periods...")
            count = import_seed_periods(session)
            print(f"  -> {count} seed periods imported")
            total_imported += count

            # 2. Import NER periods
            print("\n[2/6] Importing NER periods...")
            count = import_aggregated_periods(session, data_path)
            print(f"  -> {count} NER periods imported")
            total_imported += count

            # 3. Import polities
            print("\n[3/6] Importing polities...")
            count = import_polities(session, data_path)
            print(f"  -> {count} polities imported")
            total_imported += count

            # 4. Import persons
            print("\n[4/6] Importing persons...")
            count = import_persons(session, data_path)
            print(f"  -> {count} persons imported")
            total_imported += count

            # 5. Import locations
            print("\n[5/6] Importing locations...")
            count = import_locations(session, data_path)
            print(f"  -> {count} locations imported")
            total_imported += count

            # 6. Import events
            print("\n[6/6] Importing events...")
            count = import_events(session, data_path, force_all=args.force_all)
            print(f"  -> {count} events imported")
            total_imported += count

        # Update batch record
        update_import_batch(session, batch_id, total_imported, total_imported, 0)

        print("\n" + "=" * 60)
        print(f"IMPORT COMPLETE")
        print(f"Total imported: {total_imported:,} entities")
        print(f"Finished: {datetime.now().isoformat()}")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
