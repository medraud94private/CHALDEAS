#!/usr/bin/env python3
"""Import Stanford Encyclopedia of Philosophy entries as persons with embedding."""
import sys
import os
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

DATA_FILE = Path(__file__).parent.parent.parent / "raw" / "stanford_encyclopedia" / "sep_entries.json"

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)

def generate_slug(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-')[:100]

def truncate_content(content: str, max_chars: int = 15000) -> str:
    """Truncate content to fit in biography field."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "..."


def get_embedding(client, text: str, model: str = "text-embedding-3-small") -> list:
    """Get embedding for text."""
    text = text[:8000]  # Limit text length
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


def embed_new_persons(conn, imported_ids: list):
    """Embed newly imported persons."""
    if not HAS_OPENAI or not imported_ids:
        print("Skipping embedding (no OpenAI or no new imports)")
        return

    client = OpenAI()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print(f"\nEmbedding {len(imported_ids)} new persons...")
    embedded = 0

    for i, pid in enumerate(imported_ids):
        cur.execute("SELECT name, biography FROM persons WHERE id = %s", (pid,))
        person = cur.fetchone()
        if not person:
            continue

        text = f"{person['name']}: {person['biography'][:5000]}"

        try:
            embedding = get_embedding(client, text)
            cur.execute(
                "UPDATE persons SET embedding = %s WHERE id = %s",
                (str(embedding), pid)
            )
            embedded += 1

            if embedded % 20 == 0:
                conn.commit()
                print(f"  Embedded: {embedded}/{len(imported_ids)}")

        except Exception as e:
            print(f"  Error embedding {pid}: {e}")
            continue

    conn.commit()
    print(f"Embedded: {embedded} persons")

def main():
    print("=" * 60)
    print("Import Stanford Encyclopedia of Philosophy")
    print("=" * 60)

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    print(f"Loaded: {len(entries)} entries")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print("Database connected!")

    # Get existing names
    cur.execute("SELECT LOWER(name) FROM persons")
    existing = {row['lower'] for row in cur.fetchall() if row['lower']}
    print(f"Existing persons: {len(existing):,}")

    # Get or create philosophy category
    cur.execute("SELECT id FROM categories WHERE slug = 'philosophy'")
    result = cur.fetchone()
    if result:
        philosophy_cat_id = result['id']
    else:
        cur.execute("""
            INSERT INTO categories (name, slug, created_at, updated_at)
            VALUES ('Philosophy', 'philosophy', NOW(), NOW())
            RETURNING id
        """)
        philosophy_cat_id = cur.fetchone()['id']
        conn.commit()
    print(f"Philosophy category ID: {philosophy_cat_id}")

    imported = 0
    skipped = 0
    imported_ids = []

    for i, entry in enumerate(entries):
        title = entry.get('title', '').strip()
        if not title:
            skipped += 1
            continue

        # Skip if already exists
        if title.lower() in existing:
            skipped += 1
            continue

        # Get content (abstract + first part of content)
        abstract = entry.get('abstract', '')
        content = entry.get('content', '')

        # Build biography
        bio = abstract if abstract else truncate_content(content)
        if not bio:
            skipped += 1
            continue

        url = entry.get('url', '')

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, category_id, wikipedia_url, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (title, generate_slug(title), bio, philosophy_cat_id, url))
            new_id = cur.fetchone()['id']
            imported_ids.append(new_id)
            imported += 1
            existing.add(title.lower())
        except Exception as e:
            conn.rollback()
            continue

        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  Processed {i+1}/{len(entries)}... (imported: {imported})")

    conn.commit()
    print()
    print("=" * 60)
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print("=" * 60)

    # Embed new entries
    if imported_ids:
        embed_new_persons(conn, imported_ids)

    conn.close()

if __name__ == "__main__":
    main()
