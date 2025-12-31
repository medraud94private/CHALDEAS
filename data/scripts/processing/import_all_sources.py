#!/usr/bin/env python3
"""
Import All Collected Data Sources

Imports data from all collected sources into the database.
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

DATA_DIR = Path(__file__).parent.parent.parent / "raw"


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def generate_slug(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:100]


def get_existing_names(conn, table: str, name_field: str = 'name') -> set:
    cur = conn.cursor()
    cur.execute(f"SELECT LOWER({name_field}) FROM {table}")
    return {row[0] for row in cur.fetchall() if row[0]}


def ensure_category(conn, slug: str, name: str) -> int:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM categories WHERE slug = %s", (slug,))
    result = cur.fetchone()
    if result:
        return result['id']
    cur.execute("""
        INSERT INTO categories (name, slug, created_at, updated_at)
        VALUES (%s, %s, NOW(), NOW()) RETURNING id
    """, (name, slug))
    conn.commit()
    return cur.fetchone()['id']


# ============================================================
# FGO Servants (atlas_academy)
# ============================================================
def import_fgo_servants(conn):
    print("\n--- Importing FGO Servants (atlas_academy) ---")

    servants_file = DATA_DIR / "atlas_academy" / "servants_basic_na.json"
    if not servants_file.exists():
        servants_file = DATA_DIR / "atlas_academy" / "servants_na.json"
    if not servants_file.exists():
        print("  No servants file found")
        return 0

    with open(servants_file, 'r', encoding='utf-8') as f:
        servants = json.load(f)

    if isinstance(servants, dict):
        servants = list(servants.values())

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for servant in servants:
        name = servant.get('name', '').strip()
        if not name or name.lower() in existing:
            continue

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), f"FGO Servant. Class: {servant.get('className', 'Unknown')}"))
            imported += 1
            existing.add(name.lower())
        except Exception as e:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Greek Mythology (theoi)
# ============================================================
def import_theoi(conn):
    print("\n--- Importing Greek Mythology (theoi) ---")

    theoi_file = DATA_DIR / "theoi" / "theoi_figures_detailed.json"
    if not theoi_file.exists():
        print("  No theoi file found")
        return 0

    with open(theoi_file, 'r', encoding='utf-8') as f:
        figures = json.load(f)

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for fig in figures:
        name = fig.get('name', '').strip()
        if not name or name.lower() in existing:
            continue

        desc = fig.get('description', '') or fig.get('content', '')[:500] if fig.get('content') else ''

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), f"Greek mythology figure. {desc}"))
            imported += 1
            existing.add(name.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Stanford Encyclopedia (philosophers)
# ============================================================
def import_stanford(conn):
    print("\n--- Importing Stanford Encyclopedia ---")

    stanford_file = DATA_DIR / "stanford_encyclopedia" / "sep_entries.json"
    if not stanford_file.exists():
        print("  No stanford file found")
        return 0

    with open(stanford_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for article in articles:
        title = article.get('title', '').strip()
        # Only import if it looks like a person name (not a concept)
        if not title or title.lower() in existing:
            continue

        # Skip concepts (usually longer titles)
        if len(title.split()) > 4:
            continue

        content = article.get('abstract', '') or article.get('content', '') or ''
        content = content[:1000] if content else ''

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (title, generate_slug(title), f"Philosopher. {content[:500]}"))
            imported += 1
            existing.add(title.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# DBpedia Events
# ============================================================
def import_dbpedia_events(conn):
    print("\n--- Importing DBpedia Events ---")

    dbpedia_file = DATA_DIR / "dbpedia" / "dbpedia_events.json"
    if not dbpedia_file.exists():
        print("  No dbpedia events file found")
        return 0

    with open(dbpedia_file, 'r', encoding='utf-8') as f:
        events = json.load(f)

    existing = get_existing_names(conn, 'events', 'title')
    cur = conn.cursor()
    imported = 0

    for event in events:
        name = event.get('name', '').strip()
        if not name or name.lower() in existing or name.startswith('Q'):
            continue

        desc = event.get('description', '') or ''

        try:
            cur.execute("""
                INSERT INTO events (title, slug, description, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), desc))
            imported += 1
            existing.add(name.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# World History
# ============================================================
def import_worldhistory(conn):
    print("\n--- Importing World History ---")

    wh_file = DATA_DIR / "worldhistory" / "worldhistory_articles.json"
    if not wh_file.exists():
        print("  No worldhistory file found")
        return 0

    with open(wh_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    # These are articles, not events - but we can extract topics
    existing = get_existing_names(conn, 'events', 'title')
    cur = conn.cursor()
    imported = 0

    for article in articles:
        title = article.get('title', '').strip()
        if not title or title.lower() in existing:
            continue

        # Clean title
        title = re.sub(r'^Articleby.*?(?=[A-Z])', '', title)
        if len(title) < 5:
            continue

        content = article.get('content', '')[:500] if article.get('content') else ''

        try:
            cur.execute("""
                INSERT INTO events (title, slug, description, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (title[:200], generate_slug(title), content))
            imported += 1
            existing.add(title.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Arthurian Legends
# ============================================================
def import_arthurian(conn):
    print("\n--- Importing Arthurian Legends ---")

    arth_file = DATA_DIR / "arthurian" / "arthurian_wikipedia.json"
    if not arth_file.exists():
        print("  No arthurian file found")
        return 0

    with open(arth_file, 'r', encoding='utf-8') as f:
        characters = json.load(f)

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for char in characters:
        name = char.get('title', '') or char.get('name', '')
        name = name.strip()
        if not name or name.lower() in existing:
            continue

        desc = char.get('extract', '') or char.get('description', '') or ''
        desc = desc[:500] if desc else ''

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), f"Arthurian legend figure. {desc}"))
            imported += 1
            existing.add(name.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Indian Mythology
# ============================================================
def import_indian_mythology(conn):
    print("\n--- Importing Indian Mythology ---")

    for fname in ['indian_wikipedia.json', 'indian_by_category.json']:
        myth_file = DATA_DIR / "indian_mythology" / fname
        if myth_file.exists():
            break
    else:
        print("  No indian mythology file found")
        return 0

    with open(myth_file, 'r', encoding='utf-8') as f:
        figures = json.load(f)

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for fig in figures:
        name = fig.get('title', '') or fig.get('name', '')
        name = name.strip()
        if not name or name.lower() in existing:
            continue

        desc = fig.get('extract', '') or fig.get('description', '') or ''
        desc = desc[:500] if desc else ''

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), f"Indian mythology figure. {desc}"))
            imported += 1
            existing.add(name.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Mesoamerican
# ============================================================
def import_mesoamerican(conn):
    print("\n--- Importing Mesoamerican ---")

    meso_file = DATA_DIR / "mesoamerican" / "mesoamerican_wikipedia.json"
    if not meso_file.exists():
        meso_file = DATA_DIR / "mesoamerican" / "mesoamerican_deities.json"
    if not meso_file.exists():
        print("  No mesoamerican file found")
        return 0

    with open(meso_file, 'r', encoding='utf-8') as f:
        figures = json.load(f)

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for fig in figures:
        name = fig.get('title', '') or fig.get('name', '')
        name = name.strip()
        if not name or name.lower() in existing:
            continue

        desc = fig.get('extract', '') or fig.get('description', '') or ''
        desc = desc[:500] if desc else ''

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), f"Mesoamerican figure. {desc}"))
            imported += 1
            existing.add(name.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Russian History
# ============================================================
def import_russian_history(conn):
    print("\n--- Importing Russian History ---")

    rus_file = DATA_DIR / "russian_history" / "russian_wikipedia.json"
    if not rus_file.exists():
        rus_file = DATA_DIR / "russian_history" / "russian_categorized.json"
    if not rus_file.exists():
        print("  No russian history file found")
        return 0

    with open(rus_file, 'r', encoding='utf-8') as f:
        figures = json.load(f)

    existing = get_existing_names(conn, 'persons')
    cur = conn.cursor()
    imported = 0

    for fig in figures:
        name = fig.get('title', '') or fig.get('name', '')
        name = name.strip()
        if not name or name.lower() in existing:
            continue

        desc = fig.get('extract', '') or fig.get('description', '') or ''
        desc = desc[:500] if desc else ''

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), f"Russian historical figure. {desc}"))
            imported += 1
            existing.add(name.lower())
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Imported: {imported}")
    return imported


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("Import All Collected Data Sources")
    print("=" * 60)

    conn = get_db_connection()
    print("Database connected!")

    total = 0

    # Import each source
    total += import_fgo_servants(conn)
    total += import_theoi(conn)
    total += import_stanford(conn)
    total += import_dbpedia_events(conn)
    total += import_worldhistory(conn)
    total += import_arthurian(conn)
    total += import_indian_mythology(conn)
    total += import_mesoamerican(conn)
    total += import_russian_history(conn)

    print()
    print("=" * 60)
    print(f"TOTAL IMPORTED: {total:,}")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
