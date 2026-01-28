"""
Entity Normalization Script
책 추출 데이터의 인물명을 정규화하고 Wikidata QID 연결

Usage:
    python normalize_entities.py --category arthurian --model ollama
    python normalize_entities.py --category arthurian --model gpt-5.1-chat-latest
"""

import json
import asyncio
import argparse
import os
from pathlib import Path
from collections import defaultdict
import httpx

# Load .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
RESULTS_DIR = BASE_DIR / "poc" / "data" / "book_samples" / "extraction_results"
CANONICAL_MAPS_DIR = BASE_DIR / "data" / "canonical_maps"
OUTPUT_DIR = BASE_DIR / "poc" / "data" / "normalized"

# Ensure directories exist
CANONICAL_MAPS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Category keywords for filtering books
CATEGORY_KEYWORDS = {
    "arthurian": ["arthur", "grail", "lancelot", "gawain", "merlin", "morte", "round_table", "camelot", "excalibur"],
    "greek": ["iliad", "odyssey", "homer", "troy", "achilles", "odysseus", "greek", "argonaut"],
    "norse": ["edda", "nibelung", "sigurd", "volsung", "odin", "thor", "viking", "norse"],
    "celtic": ["cuchulain", "ulster", "irish", "celtic", "finn", "ossian"],
    "indian": ["mahabharata", "ramayana", "yoga", "valmiki", "vyasa"],
}

# Ollama settings
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_0"


def get_books_by_category(category: str) -> list[Path]:
    """Get extraction result files for a category"""
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if not keywords:
        print(f"Unknown category: {category}")
        return []

    books = []
    for f in RESULTS_DIR.glob("*_extraction.json"):
        name_lower = f.stem.lower()
        if any(kw in name_lower for kw in keywords):
            books.append(f)

    return books


def extract_unique_persons(books: list[Path]) -> dict[str, list[str]]:
    """Extract unique person names from books, tracking which books they appear in"""
    person_to_books = defaultdict(list)

    for book_path in books:
        try:
            data = json.loads(book_path.read_text(encoding='utf-8'))
            book_id = data.get('book_id', book_path.stem)
            persons = data.get('persons', [])

            for person in persons:
                person_to_books[person].append(book_id)
        except Exception as e:
            print(f"Error reading {book_path}: {e}")

    return dict(person_to_books)


def extract_person_chunks(books: list[Path]) -> dict[str, dict[str, list[int]]]:
    """Extract which chunks each person appears in per book"""
    # Returns: {book_id: {person_name: [chunk_ids]}}
    book_person_chunks = defaultdict(lambda: defaultdict(list))

    for book_path in books:
        try:
            data = json.loads(book_path.read_text(encoding='utf-8'))
            book_id = data.get('book_id', book_path.stem)

            for chunk in data.get('chunk_results', []):
                chunk_id = chunk.get('chunk_id', 0)
                for person in chunk.get('persons', []):
                    book_person_chunks[book_id][person].append(chunk_id)
        except Exception as e:
            print(f"Error reading {book_path}: {e}")

    return dict(book_person_chunks)


def build_normalization_prompt(persons: list[str], category: str) -> str:
    """Build prompt for LLM normalization"""
    category_desc = {
        "arthurian": "Arthurian legends (King Arthur, Knights of the Round Table)",
        "greek": "Greek mythology and epics (Iliad, Odyssey, Greek gods)",
        "norse": "Norse mythology (Eddas, Nibelungenlied, Viking sagas)",
        "celtic": "Celtic/Irish mythology (Ulster Cycle, Fenian Cycle)",
        "indian": "Indian epics (Mahabharata, Ramayana)",
    }

    persons_json = json.dumps(persons[:50], ensure_ascii=False, indent=2)  # Batch of 50

    return f"""You are an entity normalization expert for historical and mythological figures.

Category: {category_desc.get(category, category)}

Given these person names extracted from books, identify:
1. The canonical English name (most common spelling)
2. Wikidata QID if you know it (format: Q12345)
3. Confidence score (0.0-1.0)

Input names:
{persons_json}

Rules:
- Use the most common English spelling as canonical
- For titles (Sir, King, Queen, Dame, Lord), remove them for canonical but note the title
- If it's a generic term (e.g., "King", "Knight", "Warrior") or unclear, set canonical to null
- Group obvious variations (Gawain/Gawaine/Gauvain → Gawain)

Respond with valid JSON array only, no other text:
[
  {{"extracted": "Dame Guinevere", "canonical": "Guinevere", "wikidata_qid": "Q43064", "confidence": 0.99}},
  {{"extracted": "the King", "canonical": null, "wikidata_qid": null, "confidence": 0.0}},
  ...
]
"""


async def call_ollama(prompt: str) -> str:
    """Call Ollama API"""
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_gpu": 30, "num_ctx": 8192}
                }
            )
            data = response.json()
            result = data.get("response", "")
            if not result:
                print(f"    [Ollama] Empty response. Status: {response.status_code}")
            return result
        except Exception as e:
            print(f"    [Ollama] API Error: {e}")
            return ""


async def call_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Call OpenAI API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    # Use model as-is (gpt-5.1-chat-latest, gpt-5-mini, etc.)
    actual_model = model

    # Build request payload - gpt-5.1 doesn't support temperature param
    payload = {
        "model": actual_model,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Only add temperature for non-5.1 models
    if "5.1" not in model and "5-" not in model:
        payload["temperature"] = 0.1

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload
            )
            data = response.json()

            if "error" in data:
                print(f"    [OpenAI] Error: {data['error'].get('message', data['error'])}")
                return ""

            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    [OpenAI] Exception: {e}")
            return ""


def parse_llm_response(response: str) -> list[dict]:
    """Parse LLM JSON response"""
    import re

    if not response:
        return []

    # Try to extract JSON from response
    response = response.strip()

    # Remove markdown code blocks if present
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        parts = response.split("```")
        if len(parts) >= 2:
            response = parts[1]

    response = response.strip()

    # Find JSON array
    start = response.find('[')
    end = response.rfind(']') + 1

    if start >= 0 and end > start:
        json_str = response[start:end]

        # Fix common LLM JSON issues:
        # 1. Unquoted QID values: Q12345 → "Q12345"
        json_str = re.sub(r':\s*(Q\d+)', r': "\1"', json_str)
        # 2. Unquoted null
        json_str = re.sub(r':\s*null\s*([,\}])', r': null\1', json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"    JSON parse error: {e}")
            print(f"    Response preview: {json_str[:200]}...")

    return []


async def normalize_batch(persons: list[str], category: str, model: str) -> list[dict]:
    """Normalize a batch of person names"""
    prompt = build_normalization_prompt(persons, category)

    if model == "ollama":
        response = await call_ollama(prompt)
    else:
        response = await call_openai(prompt, model)

    return parse_llm_response(response)


async def normalize_category(category: str, model: str = "ollama", limit: int = 0):
    """Normalize all persons in a category"""
    print(f"\n{'='*60}")
    print(f"Normalizing category: {category.upper()}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # Get books
    books = get_books_by_category(category)
    print(f"Found {len(books)} books in category")

    if not books:
        return

    # Extract unique persons
    person_to_books = extract_unique_persons(books)
    persons = list(person_to_books.keys())
    print(f"Found {len(persons)} unique person names")

    # Apply limit if specified
    if limit > 0 and limit < len(persons):
        persons = persons[:limit]
        print(f"Limited to first {limit} persons for testing")

    # Extract chunk info
    book_person_chunks = extract_person_chunks(books)

    # Process in batches (smaller batches for Ollama reliability)
    batch_size = 20 if model == "ollama" else 50
    all_normalized = []

    for i in range(0, len(persons), batch_size):
        batch = persons[i:i+batch_size]
        print(f"\nProcessing batch {i//batch_size + 1}/{(len(persons)-1)//batch_size + 1} ({len(batch)} names)...")

        try:
            normalized = await normalize_batch(batch, category, model)
            if normalized:
                all_normalized.extend(normalized)
                print(f"  Normalized {len(normalized)} names")

                # Show some examples
                for item in normalized[:3]:
                    if item.get('canonical'):
                        print(f"    {item['extracted']} → {item['canonical']} ({item.get('wikidata_qid', 'no QID')})")
            else:
                print(f"  Warning: Empty response from LLM")
        except Exception as e:
            import traceback
            print(f"  Error: {e}")
            traceback.print_exc()

        # Small delay between batches
        await asyncio.sleep(1)

    # Build canonical map
    canonical_map = {}
    for item in all_normalized:
        canonical = item.get('canonical')
        if not canonical:
            continue

        if canonical not in canonical_map:
            canonical_map[canonical] = {
                "wikidata_qid": item.get('wikidata_qid'),
                "aliases": [],
                "confidence": item.get('confidence', 0.5)
            }

        extracted = item.get('extracted')
        if extracted and extracted != canonical and extracted not in canonical_map[canonical]['aliases']:
            canonical_map[canonical]['aliases'].append(extracted)

    # Save canonical map
    map_path = CANONICAL_MAPS_DIR / f"{category}.json"
    with open(map_path, 'w', encoding='utf-8') as f:
        json.dump(canonical_map, f, ensure_ascii=False, indent=2)
    print(f"\nSaved canonical map to {map_path}")
    print(f"  {len(canonical_map)} canonical entities")

    # Build book-person relationships (with original names preserved)
    book_persons_data = []

    # Create reverse lookup: extracted → canonical
    extracted_to_canonical = {}
    for item in all_normalized:
        if item.get('canonical'):
            extracted_to_canonical[item['extracted']] = {
                'canonical': item['canonical'],
                'wikidata_qid': item.get('wikidata_qid')
            }

    for book_id, person_chunks in book_person_chunks.items():
        for extracted_name, chunk_ids in person_chunks.items():
            mapping = extracted_to_canonical.get(extracted_name, {})
            book_persons_data.append({
                "book_id": book_id,
                "extracted_name": extracted_name,
                "canonical_name": mapping.get('canonical'),
                "wikidata_qid": mapping.get('wikidata_qid'),
                "chunk_ids": sorted(set(chunk_ids)),
                "mention_count": len(chunk_ids)
            })

    # Save book-persons relationships
    bp_path = OUTPUT_DIR / f"{category}_book_persons.json"
    with open(bp_path, 'w', encoding='utf-8') as f:
        json.dump(book_persons_data, f, ensure_ascii=False, indent=2)
    print(f"Saved book-persons data to {bp_path}")
    print(f"  {len(book_persons_data)} book-person relationships")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Books processed: {len(books)}")
    print(f"Unique names extracted: {len(persons)}")
    print(f"Canonical entities: {len(canonical_map)}")
    print(f"Book-person relationships: {len(book_persons_data)}")

    # Show top entities by alias count
    print("\nTop entities by variation count:")
    sorted_entities = sorted(canonical_map.items(), key=lambda x: len(x[1]['aliases']), reverse=True)
    for name, data in sorted_entities[:10]:
        aliases = data['aliases'][:5]
        qid = data.get('wikidata_qid', '')
        print(f"  {name} ({qid}): {len(data['aliases'])} variations")
        if aliases:
            print(f"    → {', '.join(aliases)}")


async def main():
    parser = argparse.ArgumentParser(description="Entity Normalization")
    parser.add_argument("--category", type=str, default="arthurian",
                        choices=list(CATEGORY_KEYWORDS.keys()),
                        help="Category to process")
    parser.add_argument("--model", type=str, default="ollama",
                        help="Model to use (ollama or gpt-5.1-chat-latest)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of persons to process (0 = all)")
    parser.add_argument("--list-categories", action="store_true",
                        help="List available categories")

    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for cat, keywords in CATEGORY_KEYWORDS.items():
            books = get_books_by_category(cat)
            print(f"  {cat}: {len(books)} books (keywords: {', '.join(keywords[:3])}...)")
        return

    await normalize_category(args.category, args.model, args.limit)


if __name__ == "__main__":
    asyncio.run(main())
