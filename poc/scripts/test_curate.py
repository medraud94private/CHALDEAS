"""
Test Curate API Endpoints
Tests all 4 chain types: person_story, place_story, era_story, causal_chain
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models import Person, Location, Period, Event
from app.services.chain_generator import ChainGenerator
from app.schemas.chain import CurationRequest


async def setup_test_data():
    """Ensure we have test data."""
    async with async_session() as session:
        # Check if data exists
        result = await session.execute(select(Person).limit(1))
        if result.scalar_one_or_none():
            print("[OK] Test data already exists")
            return True

        print("[INFO] No test data found. Run: python scripts/seed_db.py")
        return False


async def test_person_story():
    """Test person_story chain generation."""
    print()
    print("=" * 60)
    print("Test: person_story (Socrates)")
    print("=" * 60)

    async with async_session() as session:
        # Get a person
        result = await session.execute(
            select(Person).where(Person.name.ilike("%socrates%"))
        )
        person = result.scalar_one_or_none()

        if not person:
            # Get first person
            result = await session.execute(select(Person).limit(1))
            person = result.scalar_one_or_none()

        if not person:
            print("[FAIL] No person found in database")
            return False

        print(f"Person: {person.name} (ID: {person.id})")

        # Generate chain
        generator = ChainGenerator(session)
        request = CurationRequest(
            chain_type="person_story",
            person_id=person.id,
            max_segments=3
        )

        try:
            chain = await generator.generate_chain(request)
            print(f"\nChain: {chain.title}")
            print(f"Segments: {len(chain.segments)}")
            print("-" * 40)
            for seg in chain.segments:
                print(f"  [{seg.segment_order}] {seg.narrative[:100]}...")
            print()
            print("[OK] person_story test passed")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            return False


async def test_place_story():
    """Test place_story chain generation."""
    print()
    print("=" * 60)
    print("Test: place_story (Athens)")
    print("=" * 60)

    async with async_session() as session:
        # Get a location
        result = await session.execute(
            select(Location).where(Location.name.ilike("%athens%"))
        )
        location = result.scalar_one_or_none()

        if not location:
            result = await session.execute(select(Location).limit(1))
            location = result.scalar_one_or_none()

        if not location:
            print("[FAIL] No location found in database")
            return False

        print(f"Location: {location.name} (ID: {location.id})")

        generator = ChainGenerator(session)
        request = CurationRequest(
            chain_type="place_story",
            location_id=location.id,
            year_start=-500,
            year_end=-300,
            max_segments=3
        )

        try:
            chain = await generator.generate_chain(request)
            print(f"\nChain: {chain.title}")
            print(f"Segments: {len(chain.segments)}")
            print("-" * 40)
            for seg in chain.segments:
                print(f"  [{seg.segment_order}] {seg.narrative[:100]}...")
            print()
            print("[OK] place_story test passed")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            return False


async def test_era_story():
    """Test era_story chain generation."""
    print()
    print("=" * 60)
    print("Test: era_story (Classical Greece)")
    print("=" * 60)

    async with async_session() as session:
        # Get a period
        result = await session.execute(
            select(Period).where(Period.name.ilike("%classical%"))
        )
        period = result.scalar_one_or_none()

        if not period:
            result = await session.execute(select(Period).limit(1))
            period = result.scalar_one_or_none()

        if not period:
            print("[FAIL] No period found in database")
            return False

        print(f"Period: {period.name} ({period.year_start} to {period.year_end})")

        generator = ChainGenerator(session)
        request = CurationRequest(
            chain_type="era_story",
            period_id=period.id,
            max_segments=3
        )

        try:
            chain = await generator.generate_chain(request)
            print(f"\nChain: {chain.title}")
            print(f"Segments: {len(chain.segments)}")
            print("-" * 40)
            for seg in chain.segments:
                print(f"  [{seg.segment_order}] {seg.narrative[:100]}...")
            print()
            print("[OK] era_story test passed")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            return False


async def test_causal_chain():
    """Test causal_chain generation."""
    print()
    print("=" * 60)
    print("Test: causal_chain (from -400)")
    print("=" * 60)

    async with async_session() as session:
        generator = ChainGenerator(session)
        request = CurationRequest(
            chain_type="causal_chain",
            year_start=-400,
            max_segments=3
        )

        try:
            chain = await generator.generate_chain(request)
            print(f"\nChain: {chain.title}")
            print(f"Segments: {len(chain.segments)}")
            print("-" * 40)
            for seg in chain.segments:
                print(f"  [{seg.segment_order}] {seg.narrative[:100]}...")
            print()
            print("[OK] causal_chain test passed")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            return False


async def main():
    print("=" * 60)
    print("CHALDEAS PoC - Curate API Test")
    print("=" * 60)
    print()

    # Check test data
    has_data = await setup_test_data()
    if not has_data:
        return

    results = {}

    # Test all chain types
    results["person_story"] = await test_person_story()
    results["place_story"] = await test_place_story()
    results["era_story"] = await test_era_story()
    results["causal_chain"] = await test_causal_chain()

    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print()
    print(f"Result: {passed_count}/{total_count} tests passed")


if __name__ == "__main__":
    asyncio.run(main())
