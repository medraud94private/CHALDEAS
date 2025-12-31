"""
Script to index all events into the vector store.
Run this after setting up pgvector to enable semantic search.

Usage:
    python -m app.scripts.index_events
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.embeddings import EmbeddingService, VectorStore


def load_events_from_json() -> list:
    """Load events from JSON data files."""
    events = []

    # Project root
    project_root = Path(__file__).parent.parent.parent.parent

    # Processed data paths (main sources)
    processed_paths = [
        project_root / "data" / "processed" / "events_wikidata.json",
        project_root / "data" / "processed" / "events_dbpedia.json",
    ]

    for path in processed_paths:
        if path.exists():
            print(f"Loading events from: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    events.extend(data)
                elif isinstance(data, dict) and 'events' in data:
                    events.extend(data['events'])
                elif isinstance(data, dict) and 'data' in data:
                    events.extend(data['data'])
            print(f"  Loaded {len(events)} events so far")

    # Raw wikidata events (backup)
    raw_paths = [
        project_root / "data" / "raw" / "wikidata" / "wikidata_events.json",
    ]

    if not events:
        for path in raw_paths:
            if path.exists():
                print(f"Loading raw events from: {path}")
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        events.extend(data)
                    elif isinstance(data, dict):
                        for key in ['events', 'results', 'data', 'items']:
                            if key in data:
                                events.extend(data[key])
                                break

    return events


def build_event_text(event: dict) -> str:
    """Build searchable text from event."""
    parts = []

    title = event.get('title') or event.get('label') or ''
    if title:
        parts.append(f"제목: {title}")

    description = event.get('description') or event.get('desc') or ''
    if description:
        parts.append(f"설명: {description}")

    # Date
    date_start = event.get('date_start') or event.get('year')
    if date_start:
        year = int(date_start)
        era = "BCE" if year < 0 else "CE"
        parts.append(f"시기: {abs(year)} {era}")

    # Category
    category = event.get('category')
    if category:
        if isinstance(category, dict):
            category = category.get('name') or category.get('slug')
        parts.append(f"분류: {category}")

    # Location
    location = event.get('location') or event.get('place')
    if location:
        if isinstance(location, dict):
            location = location.get('name') or location.get('label')
        parts.append(f"장소: {location}")

    return "\n".join(parts)


def build_event_metadata(event: dict) -> dict:
    """Extract metadata from event."""
    title = event.get('title') or event.get('label') or ''
    date_start = event.get('date_start') or event.get('year')

    date_str = ""
    if date_start:
        year = int(date_start)
        era = "BCE" if year < 0 else "CE"
        date_str = f"{abs(year)} {era}"

    return {
        "title": title,
        "date": date_str,
        "category": event.get('category'),
        "latitude": event.get('latitude') or event.get('lat'),
        "longitude": event.get('longitude') or event.get('lng'),
    }


def main():
    print("=" * 50)
    print("CHALDEAS Event Indexer")
    print("=" * 50)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return

    print(f"API Key: {api_key[:20]}...")

    # Initialize services
    print("\nInitializing embedding service...")
    embedding_service = EmbeddingService(
        model="small",  # Default to small for cost efficiency
        api_key=api_key
    )
    print(f"Embedding model: {embedding_service.model}")
    print(f"Embedding dimension: {embedding_service.embedding_dimension}")

    print("\nInitializing vector store...")
    vector_store = VectorStore(
        embedding_dimension=embedding_service.embedding_dimension
    )

    # Initialize database
    print("\nInitializing database (creating tables if needed)...")
    try:
        vector_store.initialize()
        print("Database initialized!")
    except Exception as e:
        print(f"ERROR initializing database: {e}")
        print("Make sure PostgreSQL with pgvector is running!")
        return

    # Load events
    print("\nLoading events from JSON...")
    events = load_events_from_json()
    print(f"Found {len(events)} events")

    if not events:
        print("No events found! Check data/json/ directory")
        return

    # Index events in batches
    batch_size = 50
    total = len(events)
    indexed = 0
    failed = 0

    print(f"\nIndexing events (batch size: {batch_size})...")

    for i in range(0, total, batch_size):
        batch = events[i:i + batch_size]

        # Prepare batch data
        items = []
        for event in batch:
            event_id = event.get('id')
            if not event_id:
                continue

            try:
                # Build text and metadata
                text = build_event_text(event)
                metadata = build_event_metadata(event)

                # Generate embedding
                embedding = embedding_service.embed_text(text)

                items.append((
                    "event",
                    int(event_id),
                    embedding,
                    text,
                    metadata
                ))
            except Exception as e:
                print(f"  Failed to embed event {event_id}: {e}")
                failed += 1

        # Batch insert
        if items:
            try:
                vector_store.upsert_embeddings_batch(items)
                indexed += len(items)
                print(f"  Indexed {indexed}/{total} events...")
            except Exception as e:
                print(f"  Batch insert failed: {e}")
                failed += len(items)

    print("\n" + "=" * 50)
    print(f"Indexing complete!")
    print(f"  Indexed: {indexed}")
    print(f"  Failed: {failed}")
    print("=" * 50)

    # Show stats
    stats = vector_store.get_stats()
    print(f"\nVector store stats: {stats}")


if __name__ == "__main__":
    main()
