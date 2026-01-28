"""
Import book extraction results to database with chunk-level attribution.

Reads extraction_results JSON files and:
1. Creates Source records for each book
2. Links extracted entities to existing DB persons/locations/events
3. Stores chunk reference in page_reference field: "Section, Chunk N/M"
4. Stores ALL chunk references in chunk_references JSONB column

Usage:
    python poc/scripts/import_book_extractions.py [--dry-run]
"""

import io
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import create_engine, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from app.models.source import Source
from app.models.person import Person
from app.models.location import Location
from app.models.event import Event
from app.models.associations import person_sources, location_sources, event_sources

# Database connection
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

# Paths
RESULTS_DIR = Path(__file__).parent.parent / "data" / "book_samples" / "extraction_results"


def normalize_name(name: str) -> str:
    """Normalize entity name for matching."""
    return name.lower().strip()


def find_matching_person(session, name: str) -> Optional[Person]:
    """Find person by name (careful matching)."""
    normalized = normalize_name(name)

    # Skip very short names (likely to cause false matches)
    if len(normalized) < 4:
        return None

    # 1. Exact match
    person = session.query(Person).filter(
        func.lower(Person.name) == normalized
    ).first()
    if person:
        return person

    # 2. Name starts with search term (e.g., "Arthur" matches "Arthur, King")
    person = session.query(Person).filter(
        func.lower(Person.name).like(f"{normalized}%")
    ).first()
    if person:
        return person

    # 3. Name ends with search term (e.g., "King Arthur")
    person = session.query(Person).filter(
        func.lower(Person.name).like(f"% {normalized}")
    ).first()
    if person:
        return person

    # 4. Full word match within name
    person = session.query(Person).filter(
        func.lower(Person.name).like(f"% {normalized} %")
    ).first()

    return person


def find_matching_location(session, name: str) -> Optional[Location]:
    """Find location by name (careful matching)."""
    normalized = normalize_name(name)

    if len(normalized) < 4:
        return None

    # 1. Exact match
    location = session.query(Location).filter(
        func.lower(Location.name) == normalized
    ).first()
    if location:
        return location

    # 2. Name starts with search term
    location = session.query(Location).filter(
        func.lower(Location.name).like(f"{normalized}%")
    ).first()
    if location:
        return location

    # 3. Name ends with search term (e.g., "Ancient Rome")
    location = session.query(Location).filter(
        func.lower(Location.name).like(f"% {normalized}")
    ).first()

    return location


def find_matching_event(session, name: str) -> Optional[Event]:
    """Find event by title (careful matching)."""
    normalized = normalize_name(name)

    if len(normalized) < 5:
        return None

    # 1. Exact match
    event = session.query(Event).filter(
        func.lower(Event.title) == normalized
    ).first()
    if event:
        return event

    # 2. Title starts with search term
    event = session.query(Event).filter(
        func.lower(Event.title).like(f"{normalized}%")
    ).first()
    if event:
        return event

    # 3. Title contains as full word
    event = session.query(Event).filter(
        func.lower(Event.title).like(f"% {normalized} %")
    ).first()

    return event


def get_or_create_source(session, book_data: dict) -> Source:
    """Get existing source or create new one."""
    book_id = book_data.get("book_id", "")
    title = book_data.get("title", book_id)
    zim_path = book_data.get("zim_path", "")
    structure = book_data.get("structure", {})

    # Extract Gutenberg ID from path
    gutenberg_id = None
    if "." in zim_path:
        gutenberg_id = zim_path.split(".")[-1]

    # Check if source exists
    existing = session.query(Source).filter(
        Source.document_id == book_id
    ).first()

    if existing:
        return existing

    # Create new source
    source = Source(
        name=title[:255],
        type="primary",
        archive_type="gutenberg",
        document_id=book_id,
        document_path=zim_path,
        title=title[:500],
        url=gutenberg_id,
        description=f"Structure: {structure.get('type', 'unknown')}, Sections: {structure.get('section_count', 0)}",
        reliability=3
    )

    session.add(source)
    session.flush()  # Get ID
    return source


def make_chunk_reference(chunk: dict, total_in_section: dict) -> str:
    """Create chunk reference string: 'Section, Chunk N/M'"""
    section = chunk.get("section", "main")
    chunk_num = chunk.get("chunk_in_section", 0) + 1  # 1-indexed
    section_total = total_in_section.get(section, 1)

    if section == "main":
        return f"Chunk {chunk_num}/{section_total}"
    else:
        return f"{section}, Chunk {chunk_num}/{section_total}"


def import_extraction(session, result_path: Path, dry_run: bool = False) -> dict:
    """Import a single extraction result with chunk-level attribution."""
    with open(result_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stats = {
        "book_id": data.get("book_id"),
        "title": data.get("title"),
        "structure_type": data.get("structure", {}).get("type", "none"),
        "total_chunks": len(data.get("chunk_results", [])),
        "persons_found": 0,
        "locations_found": 0,
        "events_found": 0,
        "persons_matched": 0,
        "locations_matched": 0,
        "events_matched": 0,
        "links_created": 0
    }

    chunk_results = data.get("chunk_results", [])

    if not chunk_results:
        # Fallback to aggregated data if no chunk results
        stats["persons_found"] = len(data.get("persons", []))
        stats["locations_found"] = len(data.get("locations", []))
        stats["events_found"] = len(data.get("events", []))
        return stats

    # Calculate total chunks per section for reference
    total_in_section = {}
    for chunk in chunk_results:
        section = chunk.get("section", "main")
        total_in_section[section] = total_in_section.get(section, 0) + 1

    if dry_run:
        # Just count matches without writing
        for chunk in chunk_results:
            for name in chunk.get("persons", []):
                stats["persons_found"] += 1
                if find_matching_person(session, name):
                    stats["persons_matched"] += 1
            for name in chunk.get("locations", []):
                stats["locations_found"] += 1
                if find_matching_location(session, name):
                    stats["locations_matched"] += 1
            for name in chunk.get("events", []):
                stats["events_found"] += 1
                if find_matching_event(session, name):
                    stats["events_matched"] += 1
        return stats

    # Create source for the book
    source = get_or_create_source(session, data)

    # Track entity-source links (only ONE link per entity per source!)
    # Key: (entity_id, source_id)
    # Value: list of ALL chunk references where entity appeared
    linked_persons = {}  # {(person_id, source_id): [chunk_ref1, chunk_ref2, ...]}
    linked_locations = {}
    linked_events = {}

    # Track unique matches for stats (count each entity only once per source)
    matched_persons = set()
    matched_locations = set()
    matched_events = set()

    # First pass: collect ALL chunk references for each entity
    for chunk in chunk_results:
        chunk_ref = make_chunk_reference(chunk, total_in_section)

        for person_name in chunk.get("persons", []):
            stats["persons_found"] += 1
            person = find_matching_person(session, person_name)
            if person:
                key = (person.id, source.id)
                if key not in linked_persons:
                    linked_persons[key] = []
                    matched_persons.add(key)
                # Add this chunk reference (avoid duplicates within same chunk)
                if chunk_ref not in linked_persons[key]:
                    linked_persons[key].append(chunk_ref)

        for loc_name in chunk.get("locations", []):
            stats["locations_found"] += 1
            location = find_matching_location(session, loc_name)
            if location:
                key = (location.id, source.id)
                if key not in linked_locations:
                    linked_locations[key] = []
                    matched_locations.add(key)
                if chunk_ref not in linked_locations[key]:
                    linked_locations[key].append(chunk_ref)

        for event_name in chunk.get("events", []):
            stats["events_found"] += 1
            event = find_matching_event(session, event_name)
            if event:
                key = (event.id, source.id)
                if key not in linked_events:
                    linked_events[key] = []
                    matched_events.add(key)
                if chunk_ref not in linked_events[key]:
                    linked_events[key].append(chunk_ref)

    stats["persons_matched"] = len(matched_persons)
    stats["locations_matched"] = len(matched_locations)
    stats["events_matched"] = len(matched_events)

    # Second pass: create ONE link per entity-source with ALL chunk references
    for (person_id, source_id), chunk_refs in linked_persons.items():
        session.execute(
            insert(person_sources).values(
                person_id=person_id,
                source_id=source_id,
                page_reference=chunk_refs[0][:100] if chunk_refs else None,  # First occurrence
                chunk_references=chunk_refs  # ALL occurrences as JSON array
            ).on_conflict_do_nothing()
        )
        stats["links_created"] += 1

    for (location_id, source_id), chunk_refs in linked_locations.items():
        session.execute(
            insert(location_sources).values(
                location_id=location_id,
                source_id=source_id,
                page_reference=chunk_refs[0][:100] if chunk_refs else None,
                chunk_references=chunk_refs
            ).on_conflict_do_nothing()
        )
        stats["links_created"] += 1

    for (event_id, source_id), chunk_refs in linked_events.items():
        session.execute(
            insert(event_sources).values(
                event_id=event_id,
                source_id=source_id,
                page_reference=chunk_refs[0][:100] if chunk_refs else None,
                chunk_references=chunk_refs
            ).on_conflict_do_nothing()
        )
        stats["links_created"] += 1

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import book extractions to DB")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--limit", type=int, help="Limit number of books to import")
    args = parser.parse_args()

    print("=" * 60)
    print("Book Extraction DB Import (Chunk-Level)")
    print("=" * 60)
    print(f"Results dir: {RESULTS_DIR}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Find all extraction results
    result_files = list(RESULTS_DIR.glob("*_extraction.json"))
    print(f"Found {len(result_files)} extraction results")

    if args.limit:
        result_files = result_files[:args.limit]
        print(f"Limited to {args.limit} files")

    if not result_files:
        print("No extraction results found!")
        return

    # Connect to DB
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        total_stats = {
            "books": 0,
            "persons_matched": 0,
            "locations_matched": 0,
            "events_matched": 0,
            "links_created": 0
        }

        for result_path in result_files:
            stats = import_extraction(session, result_path, args.dry_run)

            title_short = (stats['title'] or 'Unknown')[:45]
            print(f"\n{title_short}...")
            print(f"  Structure: {stats['structure_type']} ({stats['total_chunks']} chunks)")
            print(f"  Persons: {stats['persons_matched']}/{stats['persons_found']} matched")
            print(f"  Locations: {stats['locations_matched']}/{stats['locations_found']} matched")
            print(f"  Events: {stats['events_matched']}/{stats['events_found']} matched")
            if not args.dry_run:
                print(f"  Links created: {stats['links_created']}")

            total_stats["books"] += 1
            total_stats["persons_matched"] += stats["persons_matched"]
            total_stats["locations_matched"] += stats["locations_matched"]
            total_stats["events_matched"] += stats["events_matched"]
            total_stats["links_created"] += stats.get("links_created", 0)

        if not args.dry_run:
            session.commit()
            print("\n✓ Committed to database!")

        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Books processed: {total_stats['books']}")
        print(f"  Persons matched: {total_stats['persons_matched']}")
        print(f"  Locations matched: {total_stats['locations_matched']}")
        print(f"  Events matched: {total_stats['events_matched']}")
        if not args.dry_run:
            print(f"  Total links created: {total_stats['links_created']}")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
