#!/usr/bin/env python3
"""
Phase C: Vector Embedding Generation

Creates vector embeddings for semantic search using OpenAI embedding models.

Usage:
    # Using small model (default, 1536 dims, cheaper)
    python data/scripts/processing/embed_entities.py --target all --model small

    # Using large model (3072 dims, better quality)
    python data/scripts/processing/embed_entities.py --target all --model large

    # Specific targets
    python data/scripts/processing/embed_entities.py --target events
    python data/scripts/processing/embed_entities.py --target persons
    python data/scripts/processing/embed_entities.py --target locations

Cost estimate (~100K entities with ~100 tokens each = 10M tokens):
    - text-embedding-3-small: $0.02 per 1M tokens → ~$0.20
    - text-embedding-3-large: $0.13 per 1M tokens → ~$1.30
"""

import argparse
import sys
import os
import time
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor

# Check for OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("Warning: openai package not installed. Run: pip install openai")


# Embedding model configuration
EMBEDDING_MODELS = {
    "small": {
        "name": "text-embedding-3-small",
        "dimensions": 1536,
        "cost_per_million": 0.02,  # $0.02 per 1M tokens
    },
    "large": {
        "name": "text-embedding-3-large",
        "dimensions": 3072,
        "cost_per_million": 0.13,  # $0.13 per 1M tokens
    },
}

# Default model (will be set by args)
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100  # OpenAI allows up to 2048


def get_db_connection():
    """Get database connection."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else db_url}")
    return psycopg2.connect(db_url)


def get_openai_client():
    """Initialize OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=api_key)


def create_embedding(client: OpenAI, texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for a batch of texts.

    Returns list of embedding vectors.
    """
    # Clean texts
    texts = [t[:8000] if t else "" for t in texts]  # Limit token length

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    return [data.embedding for data in response.data]


def ensure_embedding_column(conn, table: str, dim: int):
    """Ensure the table has an embedding column with correct dimensions."""
    cur = conn.cursor()

    # Check if column exists and its type
    cur.execute("""
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = 'embedding'
    """, (table,))

    result = cur.fetchone()

    if not result:
        # Column doesn't exist, create it
        print(f"Adding embedding column (vector({dim})) to {table}...")
        cur.execute(f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS embedding vector({dim})
        """)
        conn.commit()
    else:
        # Column exists - check if we need to resize
        # Note: Changing dimension requires dropping and recreating
        print(f"Embedding column exists in {table}, using current schema")


def embed_events(conn, client: OpenAI, limit: int = None):
    """Generate embeddings for events."""
    print("\n" + "=" * 60)
    print("Embedding Events")
    print("=" * 60)

    ensure_embedding_column(conn, "events", EMBEDDING_DIM)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get events without embeddings
    query = """
        SELECT id, title, description
        FROM events
        WHERE embedding IS NULL
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    events = cur.fetchall()
    print(f"Events to embed: {len(events)}")

    if not events:
        return 0

    embedded = 0
    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i:i+BATCH_SIZE]

        # Create text for embedding
        texts = []
        for event in batch:
            text = f"{event['title']}. {event['description'] or ''}"
            texts.append(text)

        try:
            embeddings = create_embedding(client, texts)

            # Update database
            update_cur = conn.cursor()
            for j, event in enumerate(batch):
                update_cur.execute("""
                    UPDATE events SET embedding = %s WHERE id = %s
                """, (embeddings[j], event['id']))

            conn.commit()
            embedded += len(batch)
            print(f"  Embedded {embedded}/{len(events)} events...")

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            print(f"  Error in batch {i}: {e}")
            conn.rollback()
            time.sleep(1)

    print(f"Successfully embedded {embedded} events")
    return embedded


def embed_persons(conn, client: OpenAI, limit: int = None):
    """Generate embeddings for persons."""
    print("\n" + "=" * 60)
    print("Embedding Persons")
    print("=" * 60)

    ensure_embedding_column(conn, "persons", EMBEDDING_DIM)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get persons without embeddings
    query = """
        SELECT id, name, biography, birth_year, death_year
        FROM persons
        WHERE embedding IS NULL
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    persons = cur.fetchall()
    print(f"Persons to embed: {len(persons)}")

    if not persons:
        return 0

    embedded = 0
    for i in range(0, len(persons), BATCH_SIZE):
        batch = persons[i:i+BATCH_SIZE]

        # Create text for embedding
        texts = []
        for person in batch:
            years = ""
            if person['birth_year']:
                b = abs(person['birth_year'])
                be = "BCE" if person['birth_year'] < 0 else "CE"
                years = f" ({b} {be}"
                if person['death_year']:
                    d = abs(person['death_year'])
                    de = "BCE" if person['death_year'] < 0 else "CE"
                    years += f" - {d} {de}"
                years += ")"

            text = f"{person['name']}{years}. {person['biography'] or ''}"
            texts.append(text)

        try:
            embeddings = create_embedding(client, texts)

            # Update database
            update_cur = conn.cursor()
            for j, person in enumerate(batch):
                update_cur.execute("""
                    UPDATE persons SET embedding = %s WHERE id = %s
                """, (embeddings[j], person['id']))

            conn.commit()
            embedded += len(batch)
            print(f"  Embedded {embedded}/{len(persons)} persons...")

            time.sleep(0.1)

        except Exception as e:
            print(f"  Error in batch {i}: {e}")
            conn.rollback()
            time.sleep(1)

    print(f"Successfully embedded {embedded} persons")
    return embedded


def embed_locations(conn, client: OpenAI, limit: int = None):
    """Generate embeddings for locations."""
    print("\n" + "=" * 60)
    print("Embedding Locations")
    print("=" * 60)

    ensure_embedding_column(conn, "locations", EMBEDDING_DIM)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get locations without embeddings
    query = """
        SELECT id, name, description, type
        FROM locations
        WHERE embedding IS NULL
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    locations = cur.fetchall()
    print(f"Locations to embed: {len(locations)}")

    if not locations:
        return 0

    embedded = 0
    for i in range(0, len(locations), BATCH_SIZE):
        batch = locations[i:i+BATCH_SIZE]

        texts = []
        for loc in batch:
            loc_type = loc.get('type', '')
            text = f"{loc['name']} ({loc_type}). {loc['description'] or ''}"
            texts.append(text)

        try:
            embeddings = create_embedding(client, texts)

            update_cur = conn.cursor()
            for j, loc in enumerate(batch):
                update_cur.execute("""
                    UPDATE locations SET embedding = %s WHERE id = %s
                """, (embeddings[j], loc['id']))

            conn.commit()
            embedded += len(batch)
            print(f"  Embedded {embedded}/{len(locations)} locations...")

            time.sleep(0.1)

        except Exception as e:
            print(f"  Error in batch {i}: {e}")
            conn.rollback()
            time.sleep(1)

    print(f"Successfully embedded {embedded} locations")
    return embedded


def embed_all(conn, client: OpenAI, limit: int = None):
    """Embed all entity types."""
    total = 0

    total += embed_events(conn, client, limit)
    total += embed_persons(conn, client, limit)
    total += embed_locations(conn, client, limit)

    print("\n" + "=" * 60)
    print(f"TOTAL EMBEDDINGS: {total}")
    print("=" * 60)

    return total


def estimate_cost(conn, model_key: str = "small"):
    """Estimate embedding cost before running."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT COUNT(*) as cnt FROM events WHERE embedding IS NULL")
    events = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM persons WHERE embedding IS NULL")
    persons = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM locations WHERE embedding IS NULL")
    locations = cur.fetchone()['cnt']

    total = events + persons + locations

    # Estimate ~100 tokens per entity average
    tokens = total * 100

    # Use model-specific cost
    model_config = EMBEDDING_MODELS.get(model_key, EMBEDDING_MODELS["small"])
    cost_per_million = model_config["cost_per_million"]
    cost = (tokens / 1_000_000) * cost_per_million

    print("\n" + "=" * 60)
    print("COST ESTIMATE")
    print("=" * 60)
    print(f"Model: {model_config['name']} ({model_config['dimensions']} dims)")
    print(f"Cost per 1M tokens: ${cost_per_million}")
    print(f"Events to embed: {events:,}")
    print(f"Persons to embed: {persons:,}")
    print(f"Locations to embed: {locations:,}")
    print(f"Total entities: {total:,}")
    print(f"Estimated tokens: {tokens:,}")
    print(f"Estimated cost: ${cost:.2f}")
    print("=" * 60)

    return cost


def main():
    global EMBEDDING_MODEL, EMBEDDING_DIM

    parser = argparse.ArgumentParser(description="Vector Embedding Generator")
    parser.add_argument(
        "--target",
        choices=["events", "persons", "locations", "all"],
        default="all",
        help="Target entities to embed"
    )
    parser.add_argument(
        "--model",
        choices=["small", "large"],
        default="small",
        help="Embedding model size: small (1536 dims, cheaper) or large (3072 dims, better quality)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of entities to embed (for testing)"
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help="Only show cost estimate, don't run"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Set model configuration based on argument
    model_config = EMBEDDING_MODELS[args.model]
    EMBEDDING_MODEL = model_config["name"]
    EMBEDDING_DIM = model_config["dimensions"]

    if not HAS_OPENAI:
        print("Error: openai package required. Run: pip install openai")
        return

    print("Phase C: Vector Embedding Generation")
    print(f"Target: {args.target}")
    print(f"Model: {EMBEDDING_MODEL} ({EMBEDDING_DIM} dimensions)")

    try:
        conn = get_db_connection()
        print("Database connected!")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return

    # Show cost estimate
    estimate_cost(conn, args.model)

    if args.estimate_only:
        conn.close()
        return

    # Confirm before proceeding
    if not args.yes:
        response = input("\nProceed with embedding? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            conn.close()
            return

    try:
        client = get_openai_client()
        print("OpenAI client initialized!")
    except Exception as e:
        print(f"OpenAI initialization failed: {e}")
        conn.close()
        return

    try:
        if args.target == "all":
            embed_all(conn, client, args.limit)
        elif args.target == "events":
            embed_events(conn, client, args.limit)
        elif args.target == "persons":
            embed_persons(conn, client, args.limit)
        elif args.target == "locations":
            embed_locations(conn, client, args.limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
