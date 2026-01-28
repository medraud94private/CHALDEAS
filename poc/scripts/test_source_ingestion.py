"""
Source Ingestion Pipeline Test

Pipeline:
1. Load entity names from DB
2. Match DB names in text (free)
3. Extract new entities with LLM (local model)
4. Create relationships
"""
import asyncio
import re
import json
import httpx
from dataclasses import dataclass
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor


# ============================================================
# Config
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "chaldeas",
    "user": "chaldeas",
    "password": "chaldeas_dev"
}

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_0"  # phi3:mini, mistral:7b-instruct-q4_0 also available

# Test text 1: Einstein-Godel (should match DB)
SAMPLE_TEXT_1 = """
In 1933, Albert Einstein and Kurt Godel both fled Nazi Germany and joined the Institute
for Advanced Study in Princeton. They became close friends and were often seen walking
together on the grounds of the Institute. Their conversations ranged from physics and
mathematics to philosophy. Einstein once remarked that he went to the Institute just
to have the privilege of walking home with Godel.
"""

# Test text 2: Alpher-Bethe-Gamow (Alpher might not be in DB)
SAMPLE_TEXT_2 = """
The Alpher-Bethe-Gamow paper, published in 1948, is one of the foundational works in
Big Bang nucleosynthesis. Ralph Alpher, Hans Bethe, and George Gamow authored the paper,
which was published in Physical Review on April 1st. The paper explained how the light
elements like hydrogen and helium were formed in the early universe. Gamow famously added
Bethe's name as a pun on the Greek letters alpha, beta, gamma. The work was conducted
at George Washington University in Washington D.C.
"""


@dataclass
class MatchedEntity:
    """Entity matched from DB"""
    entity_type: str  # person, location, event
    db_id: int
    name: str
    matched_text: str


@dataclass
class NewEntity:
    """New entity extracted by LLM"""
    entity_type: str
    name: str
    context: str


# ============================================================
# Stage 2: DB-based Entity Matching
# ============================================================
def load_entity_names(conn) -> dict:
    """Load entity names from DB"""
    entities = {
        "persons": {},
        "locations": {},
        "events": {}
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Persons (limit to avoid memory issues)
        cur.execute("""
            SELECT id, name FROM persons
            WHERE name IS NOT NULL AND LENGTH(name) > 2
            ORDER BY id LIMIT 50000
        """)
        for row in cur.fetchall():
            entities["persons"][row["name"].lower()] = {
                "id": row["id"],
                "name": row["name"]
            }

        # Locations
        cur.execute("""
            SELECT id, name FROM locations
            WHERE name IS NOT NULL AND LENGTH(name) > 2
            ORDER BY id LIMIT 20000
        """)
        for row in cur.fetchall():
            entities["locations"][row["name"].lower()] = {
                "id": row["id"],
                "name": row["name"]
            }

        # Events
        cur.execute("""
            SELECT id, title FROM events
            WHERE title IS NOT NULL AND LENGTH(title) > 3
            ORDER BY id LIMIT 20000
        """)
        for row in cur.fetchall():
            entities["events"][row["title"].lower()] = {
                "id": row["id"],
                "name": row["title"]
            }

    return entities


def match_entities_in_text(text: str, entities: dict) -> list[MatchedEntity]:
    """Match DB entities in text (simple string search)"""
    matched = []
    text_lower = text.lower()

    for entity_type, name_map in entities.items():
        for name_lower, info in name_map.items():
            # Word boundary check
            pattern = r'\b' + re.escape(name_lower) + r'\b'
            if re.search(pattern, text_lower):
                matched.append(MatchedEntity(
                    entity_type=entity_type.rstrip('s'),
                    db_id=info["id"],
                    name=info["name"],
                    matched_text=name_lower
                ))

    return matched


# ============================================================
# Stage 3: Extract New Entities with LLM
# ============================================================
async def extract_new_entities_with_llm(
    text: str,
    already_matched: list[str]
) -> list[NewEntity]:
    """Extract new entities not in DB using LLM"""

    matched_names = ", ".join(already_matched) if already_matched else "none"

    prompt = f"""Extract historical persons, locations, and events from this text.

Already found in DB: {matched_names}

Only extract NEW entities not in the above list.

Text:
{text}

Respond ONLY with JSON (no explanation, no thinking):
{{
  "new_entities": [
    {{"type": "person|location|event", "name": "name", "context": "why extracted"}}
  ]
}}
"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 2000
                    }
                }
            )
            response.raise_for_status()

            result = response.json()
            llm_response = result.get("response", "")

            # Debug: show raw response
            print(f"  [DEBUG] LLM response length: {len(llm_response)}")
            if len(llm_response) < 500:
                print(f"  [DEBUG] Raw: {llm_response[:500]}")

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    new_entities = []
                    for item in data.get("new_entities", []):
                        new_entities.append(NewEntity(
                            entity_type=item.get("type", "unknown"),
                            name=item.get("name", ""),
                            context=item.get("context", "")
                        ))
                    return new_entities
                except json.JSONDecodeError as je:
                    print(f"  [ERROR] JSON parse failed: {je}")
                    print(f"  [DEBUG] JSON text: {json_match.group()[:300]}")
                    return []
            else:
                print("  [ERROR] No JSON found in response")
                return []

    except httpx.TimeoutException:
        print("[ERROR] LLM call timed out (120s)")
        return []
    except Exception as e:
        print(f"[ERROR] LLM call failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================
# Main Test
# ============================================================
async def test_pipeline(text: str, text_name: str):
    """Test pipeline"""
    print("=" * 70)
    print(f"Test: {text_name}")
    print("=" * 70)
    print()
    print(f"Text: {text.strip()[:80]}...")
    print()

    # DB connection
    print("[Stage 1] Connecting to DB...")
    conn = psycopg2.connect(**DB_CONFIG)

    # Stage 2: Load & Match
    print("[Stage 2] Loading entity names from DB...")
    entities = load_entity_names(conn)
    print(f"  - Persons: {len(entities['persons']):,}")
    print(f"  - Locations: {len(entities['locations']):,}")
    print(f"  - Events: {len(entities['events']):,}")
    print()

    print("[Stage 2] Matching entities in text...")
    matched = match_entities_in_text(text, entities)
    print(f"  Matched: {len(matched)}")
    for m in matched:
        print(f"    - [{m.entity_type:8}] {m.name} (id={m.db_id})")
    print()

    # Stage 3: LLM extraction
    print(f"[Stage 3] Extracting new entities with LLM ({OLLAMA_MODEL})...")
    matched_names = [m.name for m in matched]
    new_entities = await extract_new_entities_with_llm(text, matched_names)

    print(f"  New entities: {len(new_entities)}")
    for n in new_entities:
        ctx = n.context[:40] + "..." if len(n.context) > 40 else n.context
        print(f"    - [{n.entity_type:8}] {n.name}")
        print(f"      Context: {ctx}")
    print()

    # Summary
    print("-" * 70)
    print("Summary:")
    print(f"  - DB matched (free): {len(matched)}")
    print(f"  - LLM extracted (local): {len(new_entities)}")
    print(f"  - Total entities: {len(matched) + len(new_entities)}")
    print()

    conn.close()

    return matched, new_entities


async def main():
    print()
    print("Source Ingestion Pipeline Test")
    print("=" * 70)
    print()

    # Check Ollama
    print("Checking Ollama connection...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            print(f"  [OK] Ollama connected, model: {OLLAMA_MODEL}")
    except Exception as e:
        print(f"  [FAIL] Ollama connection failed: {e}")
        print("  Run: ollama serve")
        return

    print()

    # Test 1: Einstein-Godel (most should be in DB)
    await test_pipeline(SAMPLE_TEXT_1, "Einstein-Godel conversation")

    print()

    # Test 2: Alpher-Bethe-Gamow (Alpher might not be in DB)
    await test_pipeline(SAMPLE_TEXT_2, "Alpher-Bethe-Gamow paper")


if __name__ == "__main__":
    asyncio.run(main())
