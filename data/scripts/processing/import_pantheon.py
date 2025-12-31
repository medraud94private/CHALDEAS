#!/usr/bin/env python3
"""Import Pantheon historical figures (59,902 persons)."""
import sys
import os
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))
from dotenv import load_dotenv
load_dotenv()

import psycopg2

DATA_FILE = Path(__file__).parent.parent.parent / "raw" / "pantheon" / "pantheon_historical.json"

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

def parse_year(val) -> int:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val or val == '?':
            return None
        try:
            return int(val)
        except:
            return None
    return None

def main():
    print("=" * 60)
    print("Import Pantheon Historical Figures")
    print("=" * 60)

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        persons = json.load(f)
    print(f"Loaded: {len(persons):,} persons")

    conn = get_db_connection()
    cur = conn.cursor()
    print("Database connected!")

    # Get existing names
    cur.execute("SELECT LOWER(name) FROM persons")
    existing = {row[0] for row in cur.fetchall() if row[0]}
    print(f"Existing persons: {len(existing):,}")

    imported = 0
    skipped = 0

    for i, p in enumerate(persons):
        name = p.get('name', '').strip()
        if not name or name.lower() in existing:
            skipped += 1
            continue

        birth = parse_year(p.get('birth_year'))
        death = parse_year(p.get('death_year'))
        occupation = p.get('occupation', '')
        country = p.get('country', '')
        hpi = p.get('hpi', '')

        bio = f"{occupation}. {country}."
        if hpi:
            bio += f" Historical Popularity Index: {hpi}"

        try:
            cur.execute("""
                INSERT INTO persons (name, slug, biography, birth_year, death_year, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """, (name, generate_slug(name), bio, birth, death))
            imported += 1
            existing.add(name.lower())
        except Exception as e:
            conn.rollback()
            continue

        if (i + 1) % 5000 == 0:
            conn.commit()
            print(f"  Processed {i+1:,}/{len(persons):,}... (imported: {imported:,})")

    conn.commit()
    print()
    print("=" * 60)
    print(f"Imported: {imported:,}")
    print(f"Skipped (duplicates): {skipped:,}")
    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    main()
