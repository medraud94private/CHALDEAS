#!/usr/bin/env python3
"""
Auto-categorize Events

Categorizes events based on title/description keywords.

Categories: battle, war, politics, religion, philosophy, science, culture, civilization, discovery
"""

import sys
import os
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor


# Category definitions with keywords
CATEGORIES = {
    'battle': {
        'name': 'Battle',
        'name_ko': '전투',
        'keywords': [
            'battle of', 'siege of', 'assault on', 'attack on', 'raid on', 'sack of',
            'fall of', 'defense of', 'capture of', 'storming of', 'bombing of',
            'massacre', 'operation ', 'action of', 'engagement at', 'skirmish',
            'ambush', 'naval battle', 'air raid', 'bombardment', 'landing at',
        ],
    },
    'war': {
        'name': 'War',
        'name_ko': '전쟁',
        'keywords': [
            ' war', 'wars of', 'war between', 'conflict', 'invasion of', 'crusade',
            'rebellion', 'revolt', 'uprising', 'revolution', 'insurgency',
            'campaign', 'offensive', 'front ', 'theater', 'civil war',
        ],
    },
    'politics': {
        'name': 'Politics',
        'name_ko': '정치',
        'keywords': [
            'treaty of', 'treaty on', 'agreement', 'convention', 'constitution',
            'coronation', 'election', 'abdication', 'accession', 'congress of',
            'declaration of', 'edict of', 'law of', 'act of', 'peace of',
            'armistice', 'truce', 'ceasefire', 'conference', 'summit',
            'assassination', 'coup', 'parliament', 'senate', 'reign of',
        ],
    },
    'religion': {
        'name': 'Religion',
        'name_ko': '종교',
        'keywords': [
            'council of', 'synod of', 'reformation', 'schism', 'crusade',
            'conversion', 'martyrdom', 'canonization', 'religious', 'church',
            'temple', 'mosque', 'cathedral', 'monastery', 'pilgrimage',
        ],
    },
    'philosophy': {
        'name': 'Philosophy',
        'name_ko': '철학',
        'keywords': [
            'philosophy', 'philosophical', 'school of', 'academy', 'socratic',
            'platonic', 'aristotelian', 'stoic', 'epicurean', 'confucian',
        ],
    },
    'science': {
        'name': 'Science',
        'name_ko': '과학',
        'keywords': [
            'discovery of', 'invention of', 'experiment', 'scientific',
            'observation of', 'theory of', 'publication of', 'eclipse',
            'comet', 'supernova', 'earthquake', 'eruption', 'epidemic', 'pandemic',
        ],
    },
    'culture': {
        'name': 'Culture',
        'name_ko': '문화',
        'keywords': [
            'founding of', 'construction of', 'building of', 'creation of',
            'establishment of', 'festival', 'games', 'olympic', 'cultural',
            'art', 'music', 'literature', 'poetry', 'drama', 'theater',
        ],
    },
    'civilization': {
        'name': 'Civilization',
        'name_ko': '문명',
        'keywords': [
            'rise of', 'collapse of', 'foundation of', 'empire', 'kingdom',
            'dynasty', 'civilization', 'golden age', 'bronze age', 'iron age',
        ],
    },
    'discovery': {
        'name': 'Discovery',
        'name_ko': '발견',
        'keywords': [
            'discovery of', 'exploration of', 'voyage', 'expedition',
            'discovered', 'landing on', 'colonization of', 'first ',
        ],
    },
}


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def ensure_categories(conn) -> dict:
    """Create categories and return id mapping."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    category_ids = {}

    for slug, data in CATEGORIES.items():
        # Check if exists
        cur.execute("SELECT id FROM categories WHERE slug = %s", (slug,))
        result = cur.fetchone()

        if result:
            category_ids[slug] = result['id']
        else:
            cur.execute("""
                INSERT INTO categories (name, name_ko, slug, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (data['name'], data['name_ko'], slug))
            category_ids[slug] = cur.fetchone()['id']

    conn.commit()
    return category_ids


def categorize_event(title: str, description: str = '') -> str:
    """Determine category based on title and description."""
    text = f"{title} {description}".lower()

    # Check each category
    for slug, data in CATEGORIES.items():
        for keyword in data['keywords']:
            if keyword in text:
                return slug

    return None  # No match


def main():
    print("=" * 60)
    print("Event Auto-Categorization")
    print("=" * 60)

    conn = get_db_connection()
    print("Database connected!")

    # Ensure categories exist
    print("\nCreating categories...")
    category_ids = ensure_categories(conn)
    print(f"Categories: {list(category_ids.keys())}")

    # Get uncategorized events
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, title, description
        FROM events
        WHERE category_id IS NULL
    """)
    events = cur.fetchall()
    print(f"\nEvents to categorize: {len(events):,}")

    # Categorize
    stats = {cat: 0 for cat in CATEGORIES}
    stats['uncategorized'] = 0

    for event in events:
        category = categorize_event(event['title'], event['description'] or '')

        if category:
            cur.execute("""
                UPDATE events SET category_id = %s, updated_at = NOW()
                WHERE id = %s
            """, (category_ids[category], event['id']))
            stats[category] += 1
        else:
            stats['uncategorized'] += 1

    conn.commit()

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {cat}: {count:,}")

    conn.close()


if __name__ == "__main__":
    main()
