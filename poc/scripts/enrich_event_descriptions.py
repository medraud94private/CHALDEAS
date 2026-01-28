#!/usr/bin/env python3
"""
Enrich event descriptions by extracting relevant text from source documents.

This script:
1. Loads events with NULL descriptions from DB
2. Finds source documents from NER aggregated data
3. Extracts relevant sentences mentioning the event
4. Updates the DB with extracted descriptions
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"
)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
NER_EVENTS_PATH = PROJECT_ROOT / "poc/data/integrated_ner_full/aggregated/events.json"
SOURCE_BASE_PATH = PROJECT_ROOT / "data/raw/british_library/extracted/json"
GUTENBERG_PATH = PROJECT_ROOT / "data/raw/gutenberg"

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def normalize_name(name: str) -> str:
    """Normalize event name for matching."""
    # Remove extra whitespace, lowercase
    name = ' '.join(name.lower().split())
    # Remove common prefixes like "the"
    if name.startswith('the '):
        name = name[4:]
    return name


def load_ner_events() -> Dict[str, dict]:
    """Load NER events and index by normalized name+year and name only."""
    print("Loading NER events...")
    with open(NER_EVENTS_PATH, encoding='utf-8') as f:
        events = json.load(f)

    # Index by multiple keys for flexible matching
    index = {}
    name_only_index = {}

    for e in events:
        name = normalize_name(e['name'])
        year = e.get('year')

        # Key with year
        if year:
            key = f"{name}_{year}"
            if key not in index:
                index[key] = e

        # Key without year (fallback)
        if name not in name_only_index:
            name_only_index[name] = e

    print(f"  Loaded {len(events)} events")
    print(f"  Indexed {len(index)} name+year combinations")
    print(f"  Indexed {len(name_only_index)} unique names")
    return index, name_only_index


def find_source_file(source_id: str) -> Optional[Path]:
    """Find the source file path for a given source ID."""
    # British Library format: 003548850_02_text
    if source_id.startswith('pg'):
        # Gutenberg format: pg12345
        pg_num = source_id[2:]
        # Try different Gutenberg structures
        for subdir in ['', 'text', 'cache']:
            path = GUTENBERG_PATH / subdir / f"{pg_num}.txt"
            if path.exists():
                return path
        return None

    # British Library format
    parts = source_id.split('_')
    if len(parts) >= 2:
        folder = parts[0][:4]  # First 4 digits
        file_path = SOURCE_BASE_PATH / folder / f"{source_id}.json"
        if file_path.exists():
            return file_path

    return None


def load_source_text(source_path: Path) -> str:
    """Load text content from a source file."""
    try:
        if source_path.suffix == '.json':
            with open(source_path, encoding='utf-8') as f:
                data = json.load(f)
            # JSON format: [[page_num, text], ...]
            if isinstance(data, list):
                texts = [item[1] for item in data if len(item) > 1 and item[1]]
                return ' '.join(texts)
            return str(data)
        else:
            # Plain text
            with open(source_path, encoding='utf-8', errors='ignore') as f:
                return f.read()
    except Exception as e:
        print(f"  Error loading {source_path}: {e}")
        return ""


def extract_relevant_sentences(text: str, event_name: str, year: Optional[int] = None) -> str:
    """Extract sentences that mention the event name or year."""
    if not text:
        return ""

    # Normalize event name - get key words
    name_words = [w.lower() for w in re.split(r'\W+', event_name) if len(w) > 3]
    if not name_words:
        return ""

    # Split into sentences
    sentences = re.split(r'[.!?]+', text)

    relevant = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20 or len(sent) > 500:
            continue

        sent_lower = sent.lower()

        # Check if any key word is mentioned
        matches = sum(1 for w in name_words if w in sent_lower)
        if matches >= min(2, len(name_words)):  # At least 2 words or all if fewer
            # Check year if provided
            if year:
                if str(abs(year)) in sent:
                    relevant.insert(0, sent)  # Prioritize sentences with year
                else:
                    relevant.append(sent)
            else:
                relevant.append(sent)

    if not relevant:
        return ""

    # Take best sentences (up to 500 chars)
    result = []
    total_len = 0
    for sent in relevant[:3]:
        if total_len + len(sent) > 500:
            break
        result.append(sent)
        total_len += len(sent)

    return ' '.join(result).strip()


def process_events(batch_size: int = 1000, limit: Optional[int] = None):
    """Process events with NULL descriptions."""
    session = Session()
    ner_index, name_only_index = load_ner_events()

    # Get events with NULL description
    print("\nFetching events with NULL description...")
    query = text("""
        SELECT id, title, slug, date_start
        FROM events
        WHERE description IS NULL
        ORDER BY id
    """)
    if limit:
        query = text(f"""
            SELECT id, title, slug, date_start
            FROM events
            WHERE description IS NULL
            ORDER BY id
            LIMIT {limit}
        """)

    result = session.execute(query)
    events = result.fetchall()
    print(f"  Found {len(events)} events to process")

    updated = 0
    not_found = 0
    no_source = 0
    no_text = 0

    for i, (event_id, title, slug, date_start) in enumerate(events):
        if i > 0 and i % 500 == 0:
            session.commit()
            print(f"  Processed {i}/{len(events)} - Updated: {updated}, No source: {no_source}, No text: {no_text}")

        # Find in NER index - try multiple matching strategies
        normalized = normalize_name(title)
        ner_event = None

        # Strategy 1: Exact match with year
        if date_start:
            key = f"{normalized}_{date_start}"
            ner_event = ner_index.get(key)

        # Strategy 2: Name only match
        if not ner_event:
            ner_event = name_only_index.get(normalized)

        if not ner_event or not ner_event.get('source_docs'):
            not_found += 1
            continue

        # Try each source document
        description = None
        for source_id in ner_event['source_docs'][:3]:  # Try up to 3 sources
            source_path = find_source_file(source_id)
            if not source_path:
                continue

            text_content = load_source_text(source_path)
            if not text_content:
                continue

            description = extract_relevant_sentences(text_content, title, date_start)
            if description:
                break

        if not description:
            if not any(find_source_file(s) for s in ner_event['source_docs'][:3]):
                no_source += 1
            else:
                no_text += 1
            continue

        # Update DB
        try:
            session.execute(
                text("UPDATE events SET description = :desc, updated_at = NOW() WHERE id = :id"),
                {"desc": description[:1000], "id": event_id}
            )
            updated += 1
        except Exception as e:
            print(f"  Error updating event {event_id}: {e}")

    session.commit()
    session.close()

    print(f"\n{'='*60}")
    print(f"COMPLETED")
    print(f"  Total processed: {len(events)}")
    print(f"  Updated with description: {updated}")
    print(f"  Not found in NER data: {not_found}")
    print(f"  Source file not found: {no_source}")
    print(f"  No relevant text found: {no_text}")
    print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Enrich event descriptions from source texts')
    parser.add_argument('--limit', type=int, help='Limit number of events to process')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for commits')
    args = parser.parse_args()

    print("="*60)
    print("Event Description Enrichment")
    print("="*60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    process_events(batch_size=args.batch_size, limit=args.limit)

    print(f"\nFinished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
