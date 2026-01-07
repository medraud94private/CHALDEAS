"""
Aggregate and deduplicate NER results from batch processing.

This script:
1. Parses all output JSONL files
2. Aggregates entities by type
3. Deduplicates by normalized name
4. Outputs consolidated entity lists for DB insertion
"""
import json
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

OUTPUT_DIR = Path('C:/Projects/Chaldeas/poc/data/integrated_ner_full')
RESULT_DIR = OUTPUT_DIR / 'aggregated'


@dataclass
class PersonEntity:
    name: str
    role: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    era: Optional[str] = None
    confidence: float = 0.5
    mention_count: int = 1
    source_docs: list = field(default_factory=list)


@dataclass
class LocationEntity:
    name: str
    location_type: Optional[str] = None
    modern_name: Optional[str] = None
    confidence: float = 0.5
    mention_count: int = 1
    source_docs: list = field(default_factory=list)


@dataclass
class EventEntity:
    name: str
    year: Optional[int] = None
    persons_involved: list = field(default_factory=list)
    locations_involved: list = field(default_factory=list)
    confidence: float = 0.5
    mention_count: int = 1
    source_docs: list = field(default_factory=list)


def normalize_name(name: str) -> str:
    """Normalize entity name for deduplication."""
    # Lowercase, strip, remove extra spaces
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    # Remove common suffixes like "the Great", numbers
    # Keep for now as they might be meaningful
    return name


def merge_person(existing: PersonEntity, new_data: dict, doc_id: str) -> PersonEntity:
    """Merge new person data into existing entity."""
    existing.mention_count += 1
    if doc_id not in existing.source_docs:
        existing.source_docs.append(doc_id)

    # Update fields if new data has higher confidence or fills gaps
    new_conf = new_data.get('confidence', 0.5)
    if new_conf > existing.confidence:
        existing.confidence = new_conf
        if new_data.get('role'):
            existing.role = new_data['role']
        if new_data.get('era'):
            existing.era = new_data['era']

    # Prefer non-null years
    if existing.birth_year is None and new_data.get('birth_year'):
        existing.birth_year = new_data['birth_year']
    if existing.death_year is None and new_data.get('death_year'):
        existing.death_year = new_data['death_year']

    return existing


def merge_location(existing: LocationEntity, new_data: dict, doc_id: str) -> LocationEntity:
    """Merge new location data into existing entity."""
    existing.mention_count += 1
    if doc_id not in existing.source_docs:
        existing.source_docs.append(doc_id)

    new_conf = new_data.get('confidence', 0.5)
    if new_conf > existing.confidence:
        existing.confidence = new_conf
        if new_data.get('location_type'):
            existing.location_type = new_data['location_type']
        if new_data.get('modern_name'):
            existing.modern_name = new_data['modern_name']

    return existing


def merge_event(existing: EventEntity, new_data: dict, doc_id: str) -> EventEntity:
    """Merge new event data into existing entity."""
    existing.mention_count += 1
    if doc_id not in existing.source_docs:
        existing.source_docs.append(doc_id)

    new_conf = new_data.get('confidence', 0.5)
    if new_conf > existing.confidence:
        existing.confidence = new_conf
        if new_data.get('year'):
            existing.year = new_data['year']

    # Merge involved entities
    for p in new_data.get('persons_involved', []):
        if p not in existing.persons_involved:
            existing.persons_involved.append(p)
    for loc in new_data.get('locations_involved', []):
        if loc not in existing.locations_involved:
            existing.locations_involved.append(loc)

    return existing


def process_output_files():
    """Process all output JSONL files and aggregate entities."""
    persons: dict[str, PersonEntity] = {}
    locations: dict[str, LocationEntity] = {}
    events: dict[str, EventEntity] = {}
    polities: dict[str, dict] = {}
    periods: dict[str, dict] = {}

    total_docs = 0
    processed_docs = 0

    for batch_num in range(8):
        output_file = OUTPUT_DIR / f'minimal_batch_{batch_num:02d}_output.jsonl'

        if not output_file.exists():
            print(f'batch_{batch_num:02d}: File not found')
            continue

        batch_persons = 0
        batch_locations = 0
        batch_events = 0

        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                total_docs += 1
                result = json.loads(line)
                doc_id = result['custom_id']

                body = result.get('response', {}).get('body', {})
                content = body.get('choices', [{}])[0].get('message', {}).get('content', '')

                if not content:
                    continue

                try:
                    ext = json.loads(content)
                    processed_docs += 1
                except json.JSONDecodeError:
                    continue

                # Process persons
                for p in ext.get('persons', []):
                    name = p.get('name', '').strip()
                    if not name or len(name) < 2:
                        continue

                    norm_name = normalize_name(name)
                    batch_persons += 1

                    if norm_name in persons:
                        merge_person(persons[norm_name], p, doc_id)
                    else:
                        persons[norm_name] = PersonEntity(
                            name=name,  # Keep original casing
                            role=p.get('role'),
                            birth_year=p.get('birth_year'),
                            death_year=p.get('death_year'),
                            era=p.get('era'),
                            confidence=p.get('confidence', 0.5),
                            source_docs=[doc_id]
                        )

                # Process locations
                for loc in ext.get('locations', []):
                    name = loc.get('name', '').strip()
                    if not name or len(name) < 2:
                        continue

                    norm_name = normalize_name(name)
                    batch_locations += 1

                    if norm_name in locations:
                        merge_location(locations[norm_name], loc, doc_id)
                    else:
                        locations[norm_name] = LocationEntity(
                            name=name,
                            location_type=loc.get('location_type'),
                            modern_name=loc.get('modern_name'),
                            confidence=loc.get('confidence', 0.5),
                            source_docs=[doc_id]
                        )

                # Process events
                for ev in ext.get('events', []):
                    name = ev.get('name', '').strip()
                    if not name or len(name) < 3:
                        continue

                    norm_name = normalize_name(name)
                    batch_events += 1

                    if norm_name in events:
                        merge_event(events[norm_name], ev, doc_id)
                    else:
                        events[norm_name] = EventEntity(
                            name=name,
                            year=ev.get('year'),
                            persons_involved=ev.get('persons_involved', []),
                            locations_involved=ev.get('locations_involved', []),
                            confidence=ev.get('confidence', 0.5),
                            source_docs=[doc_id]
                        )

                # Process polities (simplified)
                for pol in ext.get('polities', []):
                    name = pol.get('name', '').strip()
                    if name:
                        norm_name = normalize_name(name)
                        if norm_name not in polities:
                            polities[norm_name] = pol

                # Process periods (simplified)
                for per in ext.get('periods', []):
                    name = per.get('name', '').strip()
                    if name:
                        norm_name = normalize_name(name)
                        if norm_name not in periods:
                            periods[norm_name] = per

        print(f'batch_{batch_num:02d}: {batch_persons:,} persons, {batch_locations:,} locations, {batch_events:,} events')

    return persons, locations, events, polities, periods, total_docs, processed_docs


def filter_by_mentions(entities: dict, min_mentions: int = 2) -> dict:
    """Filter entities by minimum mention count."""
    return {k: v for k, v in entities.items() if v.mention_count >= min_mentions}


def save_results(persons, locations, events, polities, periods):
    """Save aggregated results to JSON files."""
    RESULT_DIR.mkdir(exist_ok=True)

    # Convert dataclasses to dicts
    persons_list = [asdict(p) for p in persons.values()]
    locations_list = [asdict(loc) for loc in locations.values()]
    events_list = [asdict(ev) for ev in events.values()]

    # Sort by mention count (most mentioned first)
    persons_list.sort(key=lambda x: x['mention_count'], reverse=True)
    locations_list.sort(key=lambda x: x['mention_count'], reverse=True)
    events_list.sort(key=lambda x: x['mention_count'], reverse=True)

    with open(RESULT_DIR / 'persons.json', 'w', encoding='utf-8') as f:
        json.dump(persons_list, f, ensure_ascii=False, indent=2)

    with open(RESULT_DIR / 'locations.json', 'w', encoding='utf-8') as f:
        json.dump(locations_list, f, ensure_ascii=False, indent=2)

    with open(RESULT_DIR / 'events.json', 'w', encoding='utf-8') as f:
        json.dump(events_list, f, ensure_ascii=False, indent=2)

    with open(RESULT_DIR / 'polities.json', 'w', encoding='utf-8') as f:
        json.dump(list(polities.values()), f, ensure_ascii=False, indent=2)

    with open(RESULT_DIR / 'periods.json', 'w', encoding='utf-8') as f:
        json.dump(list(periods.values()), f, ensure_ascii=False, indent=2)

    print(f'\nResults saved to {RESULT_DIR}')


def main():
    print('=== AGGREGATING NER RESULTS ===\n')

    persons, locations, events, polities, periods, total_docs, processed_docs = process_output_files()

    print(f'\n=== RAW COUNTS ===')
    print(f'Documents: {processed_docs:,}/{total_docs:,}')
    print(f'Unique Persons: {len(persons):,}')
    print(f'Unique Locations: {len(locations):,}')
    print(f'Unique Events: {len(events):,}')
    print(f'Unique Polities: {len(polities):,}')
    print(f'Unique Periods: {len(periods):,}')

    # Filter by mentions
    persons_2plus = filter_by_mentions(persons, 2)
    locations_2plus = filter_by_mentions(locations, 2)
    events_2plus = filter_by_mentions(events, 2)

    print(f'\n=== FILTERED (2+ mentions) ===')
    print(f'Persons: {len(persons_2plus):,}')
    print(f'Locations: {len(locations_2plus):,}')
    print(f'Events: {len(events_2plus):,}')

    # Top entities
    top_persons = sorted(persons.values(), key=lambda x: x.mention_count, reverse=True)[:10]
    top_locations = sorted(locations.values(), key=lambda x: x.mention_count, reverse=True)[:10]

    print(f'\n=== TOP 10 PERSONS ===')
    for p in top_persons:
        years = f"({p.birth_year or '?'}-{p.death_year or '?'})" if p.birth_year or p.death_year else ""
        print(f'  {p.mention_count:,}x - {p.name} {years}')

    print(f'\n=== TOP 10 LOCATIONS ===')
    for loc in top_locations:
        print(f'  {loc.mention_count:,}x - {loc.name} ({loc.location_type or "?"})')

    # Save results
    save_results(persons, locations, events, polities, periods)

    # Summary stats
    print(f'\n=== SUMMARY ===')
    print(f'Total unique entities: {len(persons) + len(locations) + len(events) + len(polities) + len(periods):,}')
    print(f'High-confidence (2+ mentions): {len(persons_2plus) + len(locations_2plus) + len(events_2plus):,}')


if __name__ == '__main__':
    main()
