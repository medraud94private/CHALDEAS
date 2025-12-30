#!/usr/bin/env python3
"""
Database Import Script for CHALDEAS.

Imports processed data into PostgreSQL database.

Usage:
    python import_to_db.py --input data/processed
    python import_to_db.py --input data/processed --type events
    python import_to_db.py --clear  # Clear all data first
"""
import argparse
import asyncio
from pathlib import Path
import json
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import asyncpg
except ImportError:
    print("Please install asyncpg: pip install asyncpg")
    exit(1)


class DatabaseImporter:
    """Imports processed data into PostgreSQL."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self.stats = {
            "events_imported": 0,
            "persons_imported": 0,
            "locations_imported": 0,
            "categories_created": 0,
            "sources_created": 0,
        }

    async def connect(self):
        """Connect to database."""
        print(f"Connecting to database...")
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5,
        )
        print("Connected!")

    async def close(self):
        """Close database connection."""
        if self.pool:
            await self.pool.close()

    async def ensure_tables(self):
        """Ensure all tables exist."""
        print("Ensuring tables exist...")

        async with self.pool.acquire() as conn:
            # Categories
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    name_ko VARCHAR(100),
                    slug VARCHAR(100) UNIQUE NOT NULL,
                    color VARCHAR(7) DEFAULT '#3B82F6',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Locations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    name_ko VARCHAR(255),
                    modern_name VARCHAR(255),
                    latitude DECIMAL(10, 8) NOT NULL,
                    longitude DECIMAL(11, 8) NOT NULL,
                    location_type VARCHAR(50) NOT NULL,
                    pleiades_id VARCHAR(50),
                    wikidata_id VARCHAR(50),
                    source_type VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(name, latitude, longitude)
                )
            """)

            # Events
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    external_id VARCHAR(100) UNIQUE,
                    title VARCHAR(500) NOT NULL,
                    title_ko VARCHAR(500),
                    slug VARCHAR(500) UNIQUE NOT NULL,
                    description TEXT,
                    description_ko TEXT,
                    date_start INTEGER NOT NULL,
                    date_end INTEGER,
                    date_precision VARCHAR(20) DEFAULT 'year',
                    importance INTEGER DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
                    category_id INTEGER REFERENCES categories(id),
                    primary_location_id INTEGER REFERENCES locations(id),
                    latitude DECIMAL(10, 8),
                    longitude DECIMAL(11, 8),
                    location_source VARCHAR(50),
                    location_confidence DECIMAL(3, 2),
                    source_type VARCHAR(50) NOT NULL,
                    source_id VARCHAR(100),
                    source_url VARCHAR(500),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Persons
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id SERIAL PRIMARY KEY,
                    external_id VARCHAR(100) UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    name_ko VARCHAR(255),
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    birth_year INTEGER,
                    death_year INTEGER,
                    birth_place VARCHAR(255),
                    birth_latitude DECIMAL(10, 8),
                    birth_longitude DECIMAL(11, 8),
                    death_place VARCHAR(255),
                    death_latitude DECIMAL(10, 8),
                    death_longitude DECIMAL(11, 8),
                    occupation VARCHAR(255),
                    source_type VARCHAR(50),
                    source_id VARCHAR(100),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Event-Person relationships
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS event_persons (
                    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                    person_id INTEGER REFERENCES persons(id) ON DELETE CASCADE,
                    role VARCHAR(100),
                    PRIMARY KEY (event_id, person_id)
                )
            """)

            # Event relationships
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS event_relationships (
                    id SERIAL PRIMARY KEY,
                    event_from_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                    event_to_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                    relationship_type VARCHAR(50),
                    strength INTEGER DEFAULT 3,
                    description TEXT,
                    UNIQUE(event_from_id, event_to_id, relationship_type)
                )
            """)

            # Sources (for LAPLACE)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    url VARCHAR(500),
                    author VARCHAR(255),
                    archive_type VARCHAR(50),
                    reliability INTEGER DEFAULT 3,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(name, source_type)
                )
            """)

            # Tags
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Event tags
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS event_tags (
                    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (event_id, tag_id)
                )
            """)

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_date ON events(date_start);
                CREATE INDEX IF NOT EXISTS idx_events_location ON events(latitude, longitude);
                CREATE INDEX IF NOT EXISTS idx_events_category ON events(category_id);
                CREATE INDEX IF NOT EXISTS idx_persons_birth ON persons(birth_year);
                CREATE INDEX IF NOT EXISTS idx_locations_coords ON locations(latitude, longitude);
            """)

        print("Tables ready!")

    async def clear_all(self):
        """Clear all data from tables."""
        print("Clearing all data...")

        async with self.pool.acquire() as conn:
            await conn.execute("TRUNCATE event_tags, event_persons, event_relationships, events, persons, locations, categories, sources, tags CASCADE")

        print("Data cleared!")

    async def import_all(self, input_dir: Path):
        """Import all processed data."""
        print("\n" + "=" * 60)
        print("Importing data to database")
        print("=" * 60)

        # Create default categories
        await self._create_default_categories()

        # Import locations first (needed for foreign keys)
        for file in input_dir.glob("locations_*.json"):
            await self._import_locations(file)

        # Import events
        for file in input_dir.glob("events_*.json"):
            await self._import_events(file)

        # Import persons
        for file in input_dir.glob("persons_*.json"):
            await self._import_persons(file)

        print("\n" + "=" * 60)
        print("Import Complete!")
        print("=" * 60)
        self._print_stats()

    async def _create_default_categories(self):
        """Create default event categories."""
        categories = [
            ("battle", "전투", "battle", "#EF4444"),
            ("political", "정치", "political", "#3B82F6"),
            ("cultural", "문화", "cultural", "#8B5CF6"),
            ("religious", "종교", "religious", "#F59E0B"),
            ("scientific", "과학", "scientific", "#10B981"),
            ("natural", "자연재해", "natural", "#6B7280"),
            ("general", "일반", "general", "#64748B"),
        ]

        async with self.pool.acquire() as conn:
            for name, name_ko, slug, color in categories:
                await conn.execute("""
                    INSERT INTO categories (name, name_ko, slug, color)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (name) DO NOTHING
                """, name, name_ko, slug, color)
                self.stats["categories_created"] += 1

        print(f"  Created {len(categories)} categories")

    async def _import_locations(self, file_path: Path):
        """Import locations from file."""
        print(f"\nImporting locations from {file_path.name}...")

        with open(file_path, "r", encoding="utf-8") as f:
            locations = json.load(f)

        async with self.pool.acquire() as conn:
            for loc in locations:
                try:
                    await conn.execute("""
                        INSERT INTO locations (
                            name, name_ko, modern_name,
                            latitude, longitude, location_type,
                            pleiades_id, wikidata_id, source_type
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (name, latitude, longitude) DO UPDATE
                        SET pleiades_id = COALESCE(locations.pleiades_id, EXCLUDED.pleiades_id),
                            wikidata_id = COALESCE(locations.wikidata_id, EXCLUDED.wikidata_id)
                    """,
                        loc.get("name"),
                        loc.get("name_ko"),
                        loc.get("modern_name"),
                        loc.get("latitude"),
                        loc.get("longitude"),
                        loc.get("location_type", "unknown"),
                        loc.get("pleiades_id"),
                        loc.get("wikidata_id"),
                        loc.get("source_type"),
                    )
                    self.stats["locations_imported"] += 1
                except Exception as e:
                    print(f"    Error importing location {loc.get('name')}: {e}")

        print(f"  Imported {self.stats['locations_imported']} locations")

    async def _import_events(self, file_path: Path):
        """Import events from file."""
        print(f"\nImporting events from {file_path.name}...")

        with open(file_path, "r", encoding="utf-8") as f:
            events = json.load(f)

        async with self.pool.acquire() as conn:
            # Get category mapping
            categories = await conn.fetch("SELECT id, name FROM categories")
            category_map = {c["name"]: c["id"] for c in categories}

            for event in events:
                try:
                    # Generate slug
                    slug = self._generate_slug(event.get("title", ""))
                    if not slug:
                        continue

                    # Get category ID
                    category_id = category_map.get(event.get("category", "general"))

                    await conn.execute("""
                        INSERT INTO events (
                            external_id, title, title_ko, slug,
                            description, description_ko,
                            date_start, date_end, date_precision,
                            importance, category_id,
                            latitude, longitude,
                            location_source, location_confidence,
                            source_type, source_id, source_url
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                        ON CONFLICT (external_id) DO UPDATE
                        SET title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            latitude = COALESCE(events.latitude, EXCLUDED.latitude),
                            longitude = COALESCE(events.longitude, EXCLUDED.longitude)
                    """,
                        event.get("id"),
                        event.get("title"),
                        event.get("title_ko"),
                        slug,
                        event.get("description"),
                        event.get("description_ko"),
                        event.get("date_start"),
                        event.get("date_end"),
                        event.get("date_precision", "year"),
                        event.get("importance", 3),
                        category_id,
                        event.get("latitude"),
                        event.get("longitude"),
                        event.get("location_source"),
                        event.get("location_confidence"),
                        event.get("source_type"),
                        event.get("source_id"),
                        event.get("source_url"),
                    )
                    self.stats["events_imported"] += 1

                    # Import tags
                    for tag_name in event.get("tags", []):
                        if tag_name:
                            await self._ensure_tag(conn, tag_name)

                except Exception as e:
                    print(f"    Error importing event {event.get('title', 'unknown')[:30]}: {e}")

        print(f"  Imported {self.stats['events_imported']} events")

    async def _import_persons(self, file_path: Path):
        """Import persons from file."""
        print(f"\nImporting persons from {file_path.name}...")

        with open(file_path, "r", encoding="utf-8") as f:
            persons = json.load(f)

        async with self.pool.acquire() as conn:
            for person in persons:
                try:
                    # Generate slug
                    slug = self._generate_slug(person.get("name", ""))
                    if not slug:
                        continue

                    await conn.execute("""
                        INSERT INTO persons (
                            external_id, name, name_ko, slug,
                            description, birth_year, death_year,
                            birth_place, birth_latitude, birth_longitude,
                            death_place, death_latitude, death_longitude,
                            occupation, source_type, source_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                        ON CONFLICT (external_id) DO UPDATE
                        SET name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            birth_latitude = COALESCE(persons.birth_latitude, EXCLUDED.birth_latitude),
                            birth_longitude = COALESCE(persons.birth_longitude, EXCLUDED.birth_longitude)
                    """,
                        person.get("id"),
                        person.get("name"),
                        person.get("name_ko"),
                        slug,
                        person.get("description"),
                        person.get("birth_year"),
                        person.get("death_year"),
                        person.get("birth_place"),
                        person.get("birth_latitude"),
                        person.get("birth_longitude"),
                        person.get("death_place"),
                        person.get("death_latitude"),
                        person.get("death_longitude"),
                        person.get("occupation"),
                        person.get("source_type"),
                        person.get("source_id"),
                    )
                    self.stats["persons_imported"] += 1

                except Exception as e:
                    print(f"    Error importing person {person.get('name', 'unknown')[:30]}: {e}")

        print(f"  Imported {self.stats['persons_imported']} persons")

    async def _ensure_tag(self, conn, tag_name: str) -> int:
        """Ensure a tag exists and return its ID."""
        result = await conn.fetchrow("""
            INSERT INTO tags (name) VALUES ($1)
            ON CONFLICT (name) DO UPDATE SET name = tags.name
            RETURNING id
        """, tag_name.lower())
        return result["id"]

    def _generate_slug(self, title: str) -> str:
        """Generate URL-safe slug from title."""
        if not title:
            return ""

        import re
        import unicodedata

        # Normalize unicode
        slug = unicodedata.normalize("NFKD", title)

        # Convert to lowercase and replace spaces
        slug = slug.lower().replace(" ", "-")

        # Remove non-alphanumeric characters (except hyphens)
        slug = re.sub(r"[^a-z0-9\-]", "", slug)

        # Remove multiple hyphens
        slug = re.sub(r"-+", "-", slug)

        # Limit length
        slug = slug[:200]

        return slug.strip("-")

    def _print_stats(self):
        """Print import statistics."""
        print(f"\nStatistics:")
        print(f"  Events imported: {self.stats['events_imported']}")
        print(f"  Persons imported: {self.stats['persons_imported']}")
        print(f"  Locations imported: {self.stats['locations_imported']}")
        print(f"  Categories created: {self.stats['categories_created']}")


async def main():
    parser = argparse.ArgumentParser(description="CHALDEAS Database Importer")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed"),
        help="Input directory with processed data",
    )
    parser.add_argument(
        "--type",
        choices=["all", "events", "persons", "locations"],
        default="all",
        help="Type of data to import",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all data before import",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://chaldeas:chaldeas@localhost:5432/chaldeas"),
        help="PostgreSQL connection URL",
    )

    args = parser.parse_args()

    print("CHALDEAS Database Importer")
    print(f"Input: {args.input}")
    print(f"Database: {args.database_url.split('@')[1] if '@' in args.database_url else args.database_url}")

    importer = DatabaseImporter(args.database_url)

    try:
        await importer.connect()
        await importer.ensure_tables()

        if args.clear:
            await importer.clear_all()

        await importer.import_all(args.input)

    finally:
        await importer.close()


if __name__ == "__main__":
    asyncio.run(main())
