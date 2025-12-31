#!/usr/bin/env python3
"""
LLM-based Event Categorization using gpt-5-nano

For events that couldn't be categorized by keyword matching.
"""

import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

CATEGORIES = ['battle', 'war', 'politics', 'religion', 'philosophy', 'science', 'culture', 'civilization', 'discovery']

SYSTEM_PROMPT = """You are a historical event classifier.
Classify the given event into ONE of these categories:
- battle: Military engagements, sieges, attacks
- war: Wars, conflicts, rebellions, invasions
- politics: Treaties, laws, elections, diplomatic events
- religion: Religious events, councils, reforms
- philosophy: Philosophical movements, schools
- science: Scientific discoveries, natural phenomena, disasters
- culture: Cultural events, arts, festivals, constructions
- civilization: Rise/fall of empires, civilizations
- discovery: Explorations, discoveries, expeditions

Respond with ONLY the category name, nothing else."""


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def classify_event(client: OpenAI, title: str, description: str = '') -> str:
    """Classify event using LLM."""
    user_prompt = f"Event: {title}"
    if description:
        user_prompt += f"\nDescription: {description[:200]}"

    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=200  # gpt-5-nano uses ~128 reasoning tokens
        )

        content = response.choices[0].message.content
        if not content:
            return None
        category = content.strip().lower()

        # Validate category
        if category in CATEGORIES:
            return category

        # Try to match partial
        for cat in CATEGORIES:
            if cat in category:
                return cat

        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    print("=" * 60)
    print("LLM Event Categorization (gpt-5-nano)")
    print("=" * 60)

    # Initialize OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return

    client = OpenAI(api_key=api_key)
    print("OpenAI client initialized!")

    conn = get_db_connection()
    print("Database connected!")

    # Get category IDs
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, slug FROM categories")
    category_ids = {r['slug']: r['id'] for r in cur.fetchall()}

    # Get uncategorized events
    cur.execute("""
        SELECT id, title, description
        FROM events
        WHERE category_id IS NULL
        ORDER BY id
    """)
    events = cur.fetchall()
    print(f"\nEvents to classify: {len(events):,}")

    if not events:
        print("No uncategorized events!")
        return

    # Classify events
    stats = {cat: 0 for cat in CATEGORIES}
    stats['failed'] = 0

    for i, event in enumerate(events):
        category = classify_event(client, event['title'], event['description'] or '')

        if category and category in category_ids:
            cur.execute("""
                UPDATE events SET category_id = %s, updated_at = NOW()
                WHERE id = %s
            """, (category_ids[category], event['id']))
            stats[category] += 1
        else:
            stats['failed'] += 1

        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  Processed {i+1}/{len(events)}...")

        # Rate limiting
        time.sleep(0.05)

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
