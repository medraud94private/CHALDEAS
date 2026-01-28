"""
Analyze book extraction results before importing.

Generates a report showing:
1. Entities that match existing DB records (ready to link)
2. Entities NOT in DB (need review before creating)
3. Entities unique to single document (potentially less notable)

Usage:
    python poc/scripts/analyze_extractions.py [--limit N]
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models.person import Person
from app.models.location import Location
from app.models.event import Event

# Database connection
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

# Paths
RESULTS_DIR = Path(__file__).parent.parent / "data" / "book_samples" / "extraction_results"


def normalize_name(name: str) -> str:
    return name.lower().strip()


def load_db_entities(session):
    """Load all entity names from DB for fast lookup."""
    print("Loading DB entities...")

    # Load persons
    persons = set()
    for p in session.query(Person.name).all():
        persons.add(normalize_name(p.name))

    # Load locations
    locations = set()
    for l in session.query(Location.name).all():
        locations.add(normalize_name(l.name))

    # Load events
    events = set()
    for e in session.query(Event.title).all():
        events.add(normalize_name(e.title))

    print(f"  Persons: {len(persons):,}")
    print(f"  Locations: {len(locations):,}")
    print(f"  Events: {len(events):,}")

    return {
        "persons": persons,
        "locations": locations,
        "events": events
    }


def analyze_extraction(data: dict, db_entities: dict) -> dict:
    """Analyze one extraction result."""
    # Get all unique entities from chunks
    extracted = {
        "persons": set(),
        "locations": set(),
        "events": set()
    }

    # Track which chunks mention each entity
    entity_chunks = {
        "persons": defaultdict(list),
        "locations": defaultdict(list),
        "events": defaultdict(list)
    }

    for chunk in data.get("chunk_results", []):
        section = chunk.get("section", "main")
        chunk_num = chunk.get("chunk_in_section", 0)
        chunk_ref = f"{section}, Chunk {chunk_num+1}"

        for p in chunk.get("persons", []):
            extracted["persons"].add(p)
            entity_chunks["persons"][p].append(chunk_ref)

        for l in chunk.get("locations", []):
            extracted["locations"].add(l)
            entity_chunks["locations"][l].append(chunk_ref)

        for e in chunk.get("events", []):
            extracted["events"].add(e)
            entity_chunks["events"][e].append(chunk_ref)

    # Categorize entities
    result = {
        "title": data.get("title", "Unknown"),
        "structure": data.get("structure", {}).get("type", "none"),
        "total_chunks": len(data.get("chunk_results", [])),
        "in_db": {"persons": [], "locations": [], "events": []},
        "not_in_db": {"persons": [], "locations": [], "events": []},
        "entity_chunks": entity_chunks
    }

    for entity_type in ["persons", "locations", "events"]:
        for name in extracted[entity_type]:
            normalized = normalize_name(name)
            # Skip very short names
            if len(normalized) < 4:
                continue

            if normalized in db_entities[entity_type]:
                result["in_db"][entity_type].append(name)
            else:
                # Check partial match
                found = False
                for db_name in db_entities[entity_type]:
                    if normalized in db_name or db_name in normalized:
                        result["in_db"][entity_type].append(name)
                        found = True
                        break
                if not found:
                    result["not_in_db"][entity_type].append(name)

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze extractions before import")
    parser.add_argument("--limit", type=int, help="Limit number of books")
    parser.add_argument("--output", type=str, help="Output report file")
    args = parser.parse_args()

    print("=" * 70)
    print("Extraction Analysis Report")
    print("=" * 70)

    # Find extraction results
    result_files = sorted(RESULTS_DIR.glob("*_extraction.json"))
    print(f"Found {len(result_files)} extraction results")

    if args.limit:
        result_files = result_files[:args.limit]

    if not result_files:
        print("No extraction results found!")
        return

    # Connect to DB
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Load DB entities once
        db_entities = load_db_entities(session)

        # Track global stats
        all_not_in_db = {"persons": defaultdict(list), "locations": defaultdict(list), "events": defaultdict(list)}
        total_in_db = {"persons": 0, "locations": 0, "events": 0}
        total_not_in_db = {"persons": 0, "locations": 0, "events": 0}

        report_lines = []

        for result_path in result_files:
            with open(result_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            analysis = analyze_extraction(data, db_entities)

            # Collect stats
            for etype in ["persons", "locations", "events"]:
                total_in_db[etype] += len(analysis["in_db"][etype])
                total_not_in_db[etype] += len(analysis["not_in_db"][etype])

                for name in analysis["not_in_db"][etype]:
                    all_not_in_db[etype][name].append(analysis["title"])

            # Book summary
            title = analysis["title"][:50]
            report_lines.append(f"\n{'='*70}")
            report_lines.append(f"📖 {title}")
            report_lines.append(f"   Structure: {analysis['structure']} | Chunks: {analysis['total_chunks']}")

            report_lines.append(f"\n   ✅ In DB (ready to link):")
            report_lines.append(f"      Persons: {len(analysis['in_db']['persons'])}")
            report_lines.append(f"      Locations: {len(analysis['in_db']['locations'])}")
            report_lines.append(f"      Events: {len(analysis['in_db']['events'])}")

            report_lines.append(f"\n   ⚠️  NOT in DB (need review):")
            report_lines.append(f"      Persons: {len(analysis['not_in_db']['persons'])}")
            if analysis['not_in_db']['persons'][:5]:
                report_lines.append(f"        Examples: {analysis['not_in_db']['persons'][:5]}")
            report_lines.append(f"      Locations: {len(analysis['not_in_db']['locations'])}")
            if analysis['not_in_db']['locations'][:5]:
                report_lines.append(f"        Examples: {analysis['not_in_db']['locations'][:5]}")
            report_lines.append(f"      Events: {len(analysis['not_in_db']['events'])}")

        # Global summary
        print("\n" + "=" * 70)
        print("GLOBAL SUMMARY")
        print("=" * 70)

        print(f"\n✅ Entities IN DB (will be linked):")
        print(f"   Persons: {total_in_db['persons']}")
        print(f"   Locations: {total_in_db['locations']}")
        print(f"   Events: {total_in_db['events']}")

        print(f"\n⚠️  Entities NOT in DB (need review):")
        print(f"   Persons: {total_not_in_db['persons']}")
        print(f"   Locations: {total_not_in_db['locations']}")
        print(f"   Events: {total_not_in_db['events']}")

        # Show entities appearing in multiple books (more likely to be notable)
        print(f"\n📊 Entities NOT in DB but appear in MULTIPLE books:")
        print("   (These are more likely to be notable/real)")

        for etype in ["persons", "locations", "events"]:
            multi_book = [(name, books) for name, books in all_not_in_db[etype].items() if len(books) > 1]
            multi_book.sort(key=lambda x: -len(x[1]))

            if multi_book:
                print(f"\n   {etype.upper()} (in {len(multi_book)} multi-book entities):")
                for name, books in multi_book[:10]:
                    print(f"      {name} ({len(books)} books)")

        # Show entities only in single book
        print(f"\n📋 Entities in SINGLE book only (may need careful review):")
        for etype in ["persons", "locations", "events"]:
            single_book = [name for name, books in all_not_in_db[etype].items() if len(books) == 1]
            print(f"   {etype}: {len(single_book)} unique entities")

        # Print detailed report
        for line in report_lines:
            print(line)

        # Save report if output specified
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write("EXTRACTION ANALYSIS REPORT\n")
                f.write("=" * 70 + "\n")
                for line in report_lines:
                    f.write(line + "\n")
            print(f"\nReport saved to: {args.output}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
