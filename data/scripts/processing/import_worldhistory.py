#!/usr/bin/env python3
"""Import World History Encyclopedia articles as events with embedding."""
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

DATA_FILE = Path(__file__).parent.parent.parent / "raw" / "worldhistory" / "worldhistory_articles.json"

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
    """Truncate content to reasonable size."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "..."

def clean_title(title: str) -> str:
    """Clean article title - extract real title from merged string."""
    # Pattern: "Articleby [Author Name]TitleContent..."

    # Remove "Articleby " prefix and author name
    if title.startswith('Articleby '):
        # Pattern: "Articleby FirstName [Middle] LastNameTitleContent"
        match = re.match(r'^Articleby\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(.+)$', title)
        if match:
            rest = match.group(1)
            # Split on lowercase letter following uppercase word (content start)
            # e.g., "Daily Life in Ancient EgyptThe popular" -> split before "The popular"
            parts = re.split(r'(?<=[a-z])(?=[A-Z][a-z]+\s+[a-z])', rest, maxsplit=1)
            title = parts[0] if parts else rest[:60]
            return title[:80].strip()

    # Remove "Article" prefix
    if title.startswith('Article'):
        title = title[7:]
        # Same logic
        parts = re.split(r'(?<=[a-z])(?=[A-Z][a-z]+\s+[a-z])', title, maxsplit=1)
        title = parts[0] if parts else title[:60]

    return title[:80].strip()


def get_embedding(client, text: str, model: str = "text-embedding-3-small") -> list:
    """Get embedding for text."""
    text = text[:8000]
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


def embed_new_events(conn, imported_ids: list):
    """Embed newly imported events."""
    if not HAS_OPENAI or not imported_ids:
        print("Skipping embedding")
        return

    client = OpenAI()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print(f"\nEmbedding {len(imported_ids)} new events...")
    embedded = 0

    for i, eid in enumerate(imported_ids):
        cur.execute("SELECT title, description FROM events WHERE id = %s", (eid,))
        event = cur.fetchone()
        if not event:
            continue

        text = f"{event['title']}: {event['description'][:5000]}"

        try:
            embedding = get_embedding(client, text)
            cur.execute(
                "UPDATE events SET embedding = %s WHERE id = %s",
                (str(embedding), eid)
            )
            embedded += 1

            if embedded % 20 == 0:
                conn.commit()
                print(f"  Embedded: {embedded}/{len(imported_ids)}")

        except Exception as e:
            print(f"  Error: {e}")
            continue

    conn.commit()
    print(f"Embedded: {embedded} events")


def main():
    print("=" * 60)
    print("Import World History Encyclopedia Articles")
    print("=" * 60)

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    print(f"Loaded: {len(articles)} articles")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print("Database connected!")

    # Get existing event titles
    cur.execute("SELECT LOWER(title) FROM events")
    existing = {row['lower'] for row in cur.fetchall() if row['lower']}
    print(f"Existing events: {len(existing):,}")

    # Get or create history category
    cur.execute("SELECT id FROM categories WHERE slug = 'culture'")
    result = cur.fetchone()
    if result:
        category_id = result['id']
    else:
        cur.execute("""
            INSERT INTO categories (name, slug, created_at, updated_at)
            VALUES ('Culture', 'culture', NOW(), NOW())
            RETURNING id
        """)
        category_id = cur.fetchone()['id']
        conn.commit()
    print(f"Culture category ID: {category_id}")

    imported = 0
    skipped = 0
    imported_ids = []

    for i, article in enumerate(articles):
        raw_title = article.get('title', '').strip()
        title = clean_title(raw_title)

        if not title or len(title) < 5:
            skipped += 1
            continue

        # Skip if already exists
        if title.lower() in existing:
            skipped += 1
            continue

        content = article.get('content', '')
        if not content or len(content) < 100:
            skipped += 1
            continue

        description = truncate_content(content)
        url = article.get('url', '')

        try:
            cur.execute("""
                INSERT INTO events (title, slug, description, category_id, wikipedia_url, date_start, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 0, NOW(), NOW())
                RETURNING id
            """, (title, generate_slug(title), description, category_id, url))
            new_id = cur.fetchone()['id']
            imported_ids.append(new_id)
            imported += 1
            existing.add(title.lower())
        except Exception as e:
            print(f"  Error: {e}")
            conn.rollback()
            continue

        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  Processed {i+1}/{len(articles)}... (imported: {imported})")

    conn.commit()
    print()
    print("=" * 60)
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print("=" * 60)

    # Embed new entries
    if imported_ids:
        embed_new_events(conn, imported_ids)

    conn.close()

if __name__ == "__main__":
    main()
