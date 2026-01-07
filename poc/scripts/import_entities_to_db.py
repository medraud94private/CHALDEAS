"""
Import aggregated NER entities into the CHALDEAS database.

This script:
1. Loads aggregated & enriched entities
2. Creates slugs for persons
3. Inserts into PostgreSQL database
4. Generates and stores embeddings for vector search
"""
import os
import sys
import json
import re
import asyncio
from pathlib import Path
from typing import Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from dotenv import load_dotenv
load_dotenv()

RESULT_DIR = Path('C:/Projects/Chaldeas/poc/data/integrated_ner_full/aggregated')

# Minimum mention counts for DB insertion
MIN_PERSON_MENTIONS = 3
MIN_LOCATION_MENTIONS = 5
MIN_EVENT_MENTIONS = 3


def slugify(name: str) -> str:
    """Create URL-safe slug from name."""
    # Lowercase, replace spaces with hyphens
    slug = name.lower().strip()
    # Remove non-alphanumeric characters (except hyphens)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    # Replace spaces/multiple hyphens with single hyphen
    slug = re.sub(r'[\s-]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug[:250]  # Limit length


def load_aggregated_entities():
    """Load aggregated entities from JSON files."""
    persons = []
    locations = []
    events = []

    # Load persons
    persons_file = RESULT_DIR / 'persons.json'
    if persons_file.exists():
        with open(persons_file, 'r', encoding='utf-8') as f:
            persons = json.load(f)
        print(f'Loaded {len(persons):,} persons')

    # Load locations (prefer enriched if available)
    locations_file = RESULT_DIR / 'locations_enriched.json'
    if not locations_file.exists():
        locations_file = RESULT_DIR / 'locations.json'

    if locations_file.exists():
        with open(locations_file, 'r', encoding='utf-8') as f:
            locations = json.load(f)
        print(f'Loaded {len(locations):,} locations from {locations_file.name}')

    # Load events
    events_file = RESULT_DIR / 'events.json'
    if events_file.exists():
        with open(events_file, 'r', encoding='utf-8') as f:
            events = json.load(f)
        print(f'Loaded {len(events):,} events')

    return persons, locations, events


def filter_entities(persons, locations, events):
    """Filter entities by minimum mention count."""
    filtered_persons = [p for p in persons if p.get('mention_count', 0) >= MIN_PERSON_MENTIONS]
    filtered_locations = [loc for loc in locations if loc.get('mention_count', 0) >= MIN_LOCATION_MENTIONS]
    filtered_events = [ev for ev in events if ev.get('mention_count', 0) >= MIN_EVENT_MENTIONS]

    print(f'\nFiltered:')
    print(f'  Persons: {len(filtered_persons):,} (>={MIN_PERSON_MENTIONS} mentions)')
    print(f'  Locations: {len(filtered_locations):,} (>={MIN_LOCATION_MENTIONS} mentions)')
    print(f'  Events: {len(filtered_events):,} (>={MIN_EVENT_MENTIONS} mentions)')

    return filtered_persons, filtered_locations, filtered_events


async def import_to_database(persons, locations, events):
    """Import entities into the database."""
    from app.database import init_db, async_session, engine, Base
    from app.models import Person, Location, Event, Category
    from sqlalchemy import select, func
    from sqlalchemy.dialects.postgresql import insert

    print('\nInitializing database...')

    # Create tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Get or create a default category
        default_category = await session.execute(
            select(Category).where(Category.slug == 'historical')
        )
        default_category = default_category.scalar_one_or_none()

        if not default_category:
            default_category = Category(
                name='Historical',
                name_ko='역사',
                slug='historical',
                description='General historical entities'
            )
            session.add(default_category)
            await session.commit()
            await session.refresh(default_category)

        category_id = default_category.id

        # Import locations first (needed for person birthplace/deathplace)
        print('\nImporting locations...')
        location_ids = {}
        imported_locs = 0
        skipped_locs = 0

        for i, loc in enumerate(locations):
            name = loc.get('name', '').strip()
            if not name:
                continue

            slug = slugify(name)
            if not slug:
                continue

            # Check for coordinates
            lat = loc.get('latitude')
            lng = loc.get('longitude')

            if lat is None or lng is None:
                # Skip locations without coordinates
                skipped_locs += 1
                continue

            # Check if already exists
            existing = await session.execute(
                select(Location).where(Location.slug == slug)
            )
            existing = existing.scalar_one_or_none()

            if existing:
                location_ids[name.lower()] = existing.id
                continue

            location = Location(
                name=name,
                slug=slug,
                latitude=lat,
                longitude=lng,
                type=loc.get('location_type') or 'place',
                modern_name=loc.get('modern_name'),
                description=loc.get('geocode_display')
            )
            session.add(location)

            if (i + 1) % 100 == 0:
                await session.commit()
                print(f'  Imported {imported_locs + 100} locations...')

            imported_locs += 1

        await session.commit()
        print(f'  Imported {imported_locs} locations (skipped {skipped_locs} without coords)')

        # Build location lookup
        all_locs = await session.execute(select(Location))
        for loc in all_locs.scalars():
            location_ids[loc.name.lower()] = loc.id

        # Import persons
        print('\nImporting persons...')
        imported_persons = 0
        skipped_persons = 0

        for i, p in enumerate(persons):
            name = p.get('name', '').strip()
            if not name or len(name) < 2:
                continue

            slug = slugify(name)
            if not slug:
                continue

            # Make slug unique by adding counter if needed
            base_slug = slug
            counter = 1
            while True:
                existing = await session.execute(
                    select(Person).where(Person.slug == slug)
                )
                if not existing.scalar_one_or_none():
                    break
                counter += 1
                slug = f'{base_slug}-{counter}'
                if counter > 10:
                    skipped_persons += 1
                    break
            else:
                continue

            if counter > 10:
                continue

            person = Person(
                name=name,
                slug=slug,
                birth_year=p.get('birth_year'),
                death_year=p.get('death_year'),
                biography=p.get('role'),
                category_id=category_id
            )
            session.add(person)
            imported_persons += 1

            if (i + 1) % 500 == 0:
                await session.commit()
                print(f'  Imported {imported_persons} persons...')

        await session.commit()
        print(f'  Imported {imported_persons} persons (skipped {skipped_persons})')

        # Import events
        print('\nImporting events...')
        imported_events = 0
        skipped_events = 0

        for i, ev in enumerate(events):
            name = ev.get('name', '').strip()
            if not name or len(name) < 3:
                continue

            slug = slugify(name)
            if not slug:
                continue

            # Make slug unique
            base_slug = slug
            counter = 1
            while True:
                existing = await session.execute(
                    select(Event).where(Event.slug == slug)
                )
                if not existing.scalar_one_or_none():
                    break
                counter += 1
                slug = f'{base_slug}-{counter}'
                if counter > 10:
                    skipped_events += 1
                    break
            else:
                continue

            if counter > 10:
                continue

            # Get year
            year = ev.get('year')
            if year is None:
                year = 0  # Unknown date

            # Get primary location
            primary_location_id = None
            loc_names = ev.get('locations_involved', [])
            if loc_names:
                for loc_name in loc_names:
                    if loc_name.lower() in location_ids:
                        primary_location_id = location_ids[loc_name.lower()]
                        break

            event = Event(
                title=name,
                slug=slug,
                date_start=year,
                category_id=category_id,
                primary_location_id=primary_location_id,
                importance=min(5, max(1, ev.get('mention_count', 1) // 2))
            )
            session.add(event)
            imported_events += 1

            if (i + 1) % 500 == 0:
                await session.commit()
                print(f'  Imported {imported_events} events...')

        await session.commit()
        print(f'  Imported {imported_events} events (skipped {skipped_events})')

        # Print summary
        person_count = await session.execute(select(func.count(Person.id)))
        location_count = await session.execute(select(func.count(Location.id)))
        event_count = await session.execute(select(func.count(Event.id)))

        print(f'\n=== DATABASE SUMMARY ===')
        print(f'Total Persons: {person_count.scalar():,}')
        print(f'Total Locations: {location_count.scalar():,}')
        print(f'Total Events: {event_count.scalar():,}')


def main():
    print('=== IMPORTING ENTITIES TO DATABASE ===\n')

    # Load entities
    persons, locations, events = load_aggregated_entities()

    # Filter by mention count
    persons, locations, events = filter_entities(persons, locations, events)

    # Import to database
    asyncio.run(import_to_database(persons, locations, events))

    print('\n=== IMPORT COMPLETE ===')


if __name__ == '__main__':
    main()
