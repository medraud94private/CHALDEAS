#!/usr/bin/env python3
"""
LLM-based Entity Linking using gpt-5-nano

Links events to persons and locations using LLM understanding.
Uses vector similarity to find candidates, then LLM to verify.
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Set

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

SYSTEM_PROMPT = """You are an entity linker for historical events.
Given an event and a list of candidate persons/locations, identify which ones are DIRECTLY mentioned or involved in the event.

Rules:
- Only select entities that are explicitly mentioned or clearly involved
- Don't select entities that are merely related or from the same era
- Return a JSON object with "persons" and "locations" arrays containing the IDs of matching entities
- If no matches, return empty arrays

Example response:
{"persons": [123, 456], "locations": [789]}"""


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chaldeas')}:{os.getenv('POSTGRES_PASSWORD', 'chaldeas_dev')}@localhost:5432/{os.getenv('POSTGRES_DB', 'chaldeas')}"
    return psycopg2.connect(db_url)


def get_candidate_persons(conn, event_embedding, limit: int = 10) -> List[dict]:
    """Get candidate persons using vector similarity."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, name, biography
        FROM persons
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (event_embedding, limit))
    return cur.fetchall()


def get_candidate_locations(conn, event_embedding, limit: int = 10) -> List[dict]:
    """Get candidate locations using vector similarity."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, name, description
        FROM locations
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (event_embedding, limit))
    return cur.fetchall()


def link_event(client: OpenAI, event: dict, persons: List[dict], locations: List[dict]) -> Dict[str, List[int]]:
    """Use LLM to identify which entities are mentioned in the event."""

    # Build prompt
    event_text = f"Event: {event['title']}\nDescription: {event['description'] or 'No description'}"

    persons_text = "\n".join([
        f"- ID {p['id']}: {p['name']} ({(p['biography'] or '')[:100]})"
        for p in persons
    ])

    locations_text = "\n".join([
        f"- ID {l['id']}: {l['name']} ({(l['description'] or '')[:100]})"
        for l in locations
    ])

    user_prompt = f"""{event_text}

Candidate Persons:
{persons_text}

Candidate Locations:
{locations_text}

Which persons and locations are mentioned or directly involved in this event? Return JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=300,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        if not content:
            return {"persons": [], "locations": []}

        result = json.loads(content)
        return {
            "persons": result.get("persons", []),
            "locations": result.get("locations", [])
        }
    except Exception as e:
        print(f"  Error: {e}")
        return {"persons": [], "locations": []}


def insert_links(conn, event_id: int, person_ids: List[int], location_ids: List[int]):
    """Insert links into junction tables."""
    cur = conn.cursor()

    for person_id in person_ids:
        try:
            cur.execute("""
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES (%s, %s, 'mentioned')
                ON CONFLICT DO NOTHING
            """, (event_id, person_id))
        except Exception:
            pass

    for location_id in location_ids:
        try:
            cur.execute("""
                INSERT INTO event_locations (event_id, location_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (event_id, location_id))
        except Exception:
            pass


def main():
    print("=" * 60)
    print("LLM Entity Linking (gpt-5-nano)")
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

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get events that need linking (have embeddings but no links)
    cur.execute("""
        SELECT e.id, e.title, e.description, e.embedding::text
        FROM events e
        LEFT JOIN event_persons ep ON e.id = ep.event_id
        LEFT JOIN event_locations el ON e.id = el.event_id
        WHERE e.embedding IS NOT NULL
        AND ep.event_id IS NULL
        AND el.event_id IS NULL
        ORDER BY e.id
        LIMIT 500
    """)
    events = cur.fetchall()
    print(f"\nEvents to link: {len(events)}")

    if not events:
        print("No events need linking!")
        return

    # Stats
    stats = {
        "events_processed": 0,
        "persons_linked": 0,
        "locations_linked": 0,
        "events_with_links": 0
    }

    for i, event in enumerate(events):
        # Get candidates using vector similarity
        persons = get_candidate_persons(conn, event['embedding'], limit=15)
        locations = get_candidate_locations(conn, event['embedding'], limit=10)

        # Use LLM to verify
        links = link_event(client, event, persons, locations)

        if links['persons'] or links['locations']:
            insert_links(conn, event['id'], links['persons'], links['locations'])
            stats['persons_linked'] += len(links['persons'])
            stats['locations_linked'] += len(links['locations'])
            stats['events_with_links'] += 1

        stats['events_processed'] += 1

        if (i + 1) % 20 == 0:
            conn.commit()
            print(f"  Processed {i+1}/{len(events)}... ({stats['persons_linked']} persons, {stats['locations_linked']} locations)")

        # Rate limiting
        time.sleep(0.1)

    conn.commit()

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Events processed: {stats['events_processed']}")
    print(f"Events with links: {stats['events_with_links']}")
    print(f"Person links created: {stats['persons_linked']}")
    print(f"Location links created: {stats['locations_linked']}")

    conn.close()


if __name__ == "__main__":
    main()
