"""
Source Ingestion Pipeline Test - OpenAI Models Comparison

Compare: gpt-5.1-chat-latest, gpt-5.1-mini, gpt-5-nano
Track: quality, speed, cost
"""
import asyncio
import re
import json
import time
import os
from dataclasses import dataclass
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import AsyncOpenAI

# Load env
from dotenv import load_dotenv
load_dotenv()

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

# OpenAI models to test (prices from OpenAI pricing page)
MODELS = [
    {
        "name": "gpt-5-nano",
        "input_cost": 0.10,   # $ per 1M tokens
        "output_cost": 0.40,
    },
    {
        "name": "gpt-5-mini",
        "input_cost": 0.30,
        "output_cost": 1.20,
    },
    {
        "name": "gpt-5.1-chat-latest",
        "input_cost": 2.50,
        "output_cost": 10.00,
    },
]

# Test texts
SAMPLE_TEXT_1 = """
In 1933, Albert Einstein and Kurt Godel both fled Nazi Germany and joined the Institute
for Advanced Study in Princeton. They became close friends and were often seen walking
together on the grounds of the Institute. Their conversations ranged from physics and
mathematics to philosophy. Einstein once remarked that he went to the Institute just
to have the privilege of walking home with Godel.
"""

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
    entity_type: str
    db_id: int
    name: str
    matched_text: str


@dataclass
class NewEntity:
    entity_type: str
    name: str
    context: str


@dataclass
class ModelResult:
    model_name: str
    entities: list[NewEntity]
    input_tokens: int
    output_tokens: int
    elapsed_sec: float
    cost_usd: float


# ============================================================
# DB Matching (same as before)
# ============================================================
def load_entity_names(conn) -> dict:
    entities = {"persons": {}, "locations": {}, "events": {}}

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, name FROM persons
            WHERE name IS NOT NULL AND LENGTH(name) > 2
            ORDER BY id LIMIT 50000
        """)
        for row in cur.fetchall():
            entities["persons"][row["name"].lower()] = {"id": row["id"], "name": row["name"]}

        cur.execute("""
            SELECT id, name FROM locations
            WHERE name IS NOT NULL AND LENGTH(name) > 2
            ORDER BY id LIMIT 20000
        """)
        for row in cur.fetchall():
            entities["locations"][row["name"].lower()] = {"id": row["id"], "name": row["name"]}

        cur.execute("""
            SELECT id, title FROM events
            WHERE title IS NOT NULL AND LENGTH(title) > 3
            ORDER BY id LIMIT 20000
        """)
        for row in cur.fetchall():
            entities["events"][row["title"].lower()] = {"id": row["id"], "name": row["title"]}

    return entities


def match_entities_in_text(text: str, entities: dict) -> list[MatchedEntity]:
    matched = []
    text_lower = text.lower()

    for entity_type, name_map in entities.items():
        for name_lower, info in name_map.items():
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
# OpenAI Extraction
# ============================================================
async def extract_with_openai(
    client: AsyncOpenAI,
    model_name: str,
    text: str,
    already_matched: list[str],
    input_cost_per_m: float,
    output_cost_per_m: float
) -> ModelResult:
    """Extract entities with OpenAI model"""

    matched_names = ", ".join(already_matched) if already_matched else "none"

    prompt = f"""Extract historical persons, locations, and events from this text.

Already found in DB: {matched_names}

Only extract NEW entities not in the above list.

Text:
{text}

Respond ONLY with JSON:
{{
  "new_entities": [
    {{"type": "person|location|event", "name": "name", "context": "why extracted"}}
  ]
}}"""

    start = time.time()

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=1000
        )

        elapsed = time.time() - start

        # Token usage
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        # Cost calculation
        cost = (input_tokens / 1_000_000 * input_cost_per_m) + \
               (output_tokens / 1_000_000 * output_cost_per_m)

        # Parse response
        content = response.choices[0].message.content
        entities = []

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                for item in data.get("new_entities", []):
                    entities.append(NewEntity(
                        entity_type=item.get("type", "unknown"),
                        name=item.get("name", ""),
                        context=item.get("context", "")
                    ))
            except json.JSONDecodeError:
                pass

        return ModelResult(
            model_name=model_name,
            entities=entities,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_sec=elapsed,
            cost_usd=cost
        )

    except Exception as e:
        print(f"  [ERROR] {model_name}: {e}")
        return ModelResult(
            model_name=model_name,
            entities=[],
            input_tokens=0,
            output_tokens=0,
            elapsed_sec=time.time() - start,
            cost_usd=0
        )


# ============================================================
# Main Test
# ============================================================
async def test_all_models(text: str, text_name: str, db_entities: dict):
    """Test all OpenAI models"""
    print("=" * 80)
    print(f"Test: {text_name}")
    print("=" * 80)
    print(f"Text: {text.strip()[:60]}...")
    print()

    # DB matching first
    matched = match_entities_in_text(text, db_entities)
    print(f"[DB Match] Found {len(matched)} entities (FREE)")
    for m in matched:
        print(f"  - [{m.entity_type:8}] {m.name}")
    print()

    matched_names = [m.name for m in matched]

    # Test each model
    client = AsyncOpenAI()
    results = []

    for model_info in MODELS:
        print(f"[{model_info['name']}] Extracting...")
        result = await extract_with_openai(
            client=client,
            model_name=model_info["name"],
            text=text,
            already_matched=matched_names,
            input_cost_per_m=model_info["input_cost"],
            output_cost_per_m=model_info["output_cost"]
        )
        results.append(result)

        print(f"  Time: {result.elapsed_sec:.2f}s")
        print(f"  Tokens: {result.input_tokens} in / {result.output_tokens} out")
        print(f"  Cost: ${result.cost_usd:.6f}")
        print(f"  Entities: {len(result.entities)}")
        for e in result.entities:
            print(f"    - [{e.entity_type:8}] {e.name}")
        print()

    return matched, results


async def main():
    print()
    print("OpenAI Models Comparison Test")
    print("=" * 80)
    print()

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("[ERROR] OPENAI_API_KEY not set")
        return

    # Load DB entities once
    print("Loading DB entities...")
    conn = psycopg2.connect(**DB_CONFIG)
    db_entities = load_entity_names(conn)
    print(f"  Persons: {len(db_entities['persons']):,}")
    print(f"  Locations: {len(db_entities['locations']):,}")
    print(f"  Events: {len(db_entities['events']):,}")
    print()
    conn.close()

    all_results = []

    # Test 1
    matched1, results1 = await test_all_models(SAMPLE_TEXT_1, "Einstein-Godel", db_entities)
    all_results.extend(results1)

    print()

    # Test 2
    matched2, results2 = await test_all_models(SAMPLE_TEXT_2, "Alpher-Bethe-Gamow", db_entities)
    all_results.extend(results2)

    # Summary
    print()
    print("=" * 80)
    print("COST SUMMARY")
    print("=" * 80)
    print()
    print(f"{'Model':<25} {'Calls':>6} {'Tokens':>12} {'Time':>8} {'Cost':>12}")
    print("-" * 65)

    model_totals = {}
    for r in all_results:
        if r.model_name not in model_totals:
            model_totals[r.model_name] = {
                "calls": 0, "tokens": 0, "time": 0, "cost": 0
            }
        model_totals[r.model_name]["calls"] += 1
        model_totals[r.model_name]["tokens"] += r.input_tokens + r.output_tokens
        model_totals[r.model_name]["time"] += r.elapsed_sec
        model_totals[r.model_name]["cost"] += r.cost_usd

    for model_name, totals in model_totals.items():
        print(f"{model_name:<25} {totals['calls']:>6} {totals['tokens']:>12,} "
              f"{totals['time']:>7.2f}s ${totals['cost']:>10.6f}")

    total_cost = sum(t["cost"] for t in model_totals.values())
    print("-" * 65)
    print(f"{'TOTAL':<25} {'':<6} {'':<12} {'':<8} ${total_cost:>10.6f}")
    print()

    # Projection
    print("Cost projection (per 1000 sources):")
    for model_name, totals in model_totals.items():
        per_source = totals["cost"] / totals["calls"]
        per_1000 = per_source * 1000
        print(f"  {model_name}: ${per_1000:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
