"""
Seed script for PoC database
Loads sample data for testing
"""
import asyncio
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, async_session, engine, Base
from app.models import Period, Person, Location, Event, TextSource


async def load_sample_data():
    """Load sample data from JSON file."""
    data_path = Path(__file__).parent.parent / "data" / "seeds" / "sample_data.json"

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


async def seed_database():
    """Seed the database with sample data."""
    print("Initializing database...")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    print("Tables created.")

    # Load sample data
    data = await load_sample_data()

    async with async_session() as session:
        # Seed Periods
        print("Seeding periods...")
        for period_data in data.get("periods", []):
            period = Period(**period_data)
            session.add(period)

        # Seed Locations
        print("Seeding locations...")
        for loc_data in data.get("locations", []):
            location = Location(**loc_data)
            session.add(location)

        # Seed Persons
        print("Seeding persons...")
        for person_data in data.get("persons", []):
            person = Person(**person_data)
            session.add(person)

        # Seed Events
        print("Seeding events...")
        for event_data in data.get("events", []):
            event = Event(**event_data)
            session.add(event)

        # Seed Text Sources
        print("Seeding text sources...")
        for text_data in data.get("text_sources", []):
            text_source = TextSource(**text_data)
            session.add(text_source)

        await session.commit()
        print("Database seeded successfully!")

        # Print summary
        from sqlalchemy import select, func

        period_count = await session.execute(select(func.count(Period.id)))
        location_count = await session.execute(select(func.count(Location.id)))
        person_count = await session.execute(select(func.count(Person.id)))
        event_count = await session.execute(select(func.count(Event.id)))
        text_count = await session.execute(select(func.count(TextSource.id)))

        print(f"\nSummary:")
        print(f"  Periods: {period_count.scalar()}")
        print(f"  Locations: {location_count.scalar()}")
        print(f"  Persons: {person_count.scalar()}")
        print(f"  Events: {event_count.scalar()}")
        print(f"  Text Sources: {text_count.scalar()}")


if __name__ == "__main__":
    asyncio.run(seed_database())
