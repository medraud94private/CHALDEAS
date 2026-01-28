"""
Entity Normalization Pipeline v2
하이브리드 파이프라인: 규칙 → Wikidata → 임베딩 → LLM

Usage:
    python normalize_entities_v2.py --category arthurian
    python normalize_entities_v2.py --category arthurian --limit 100
"""

import json
import asyncio
import argparse
import os
import sys
import re
from pathlib import Path
from collections import defaultdict
from typing import Optional
import httpx

# Add backend to path for imports
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

# Load .env file
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# Paths
RESULTS_DIR = BASE_DIR / "poc" / "data" / "book_samples" / "extraction_results"
CANONICAL_MAPS_DIR = BASE_DIR / "data" / "canonical_maps"
OUTPUT_DIR = BASE_DIR / "poc" / "data" / "normalized"

# Ensure directories exist
CANONICAL_MAPS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Category keywords
CATEGORY_KEYWORDS = {
    "arthurian": ["arthur", "grail", "lancelot", "gawain", "merlin", "morte", "round_table", "camelot", "excalibur"],
    "greek": ["iliad", "odyssey", "homer", "troy", "achilles", "odysseus", "greek", "argonaut"],
    "norse": ["edda", "nibelung", "sigurd", "volsung", "odin", "thor", "viking", "norse"],
    "celtic": ["cuchulain", "ulster", "irish", "celtic", "finn", "ossian"],
    "indian": ["mahabharata", "ramayana", "yoga", "valmiki", "vyasa"],
}

# Stats tracking
class Stats:
    def __init__(self):
        self.rule_matched = 0
        self.wikidata_matched = 0
        self.embedding_matched = 0
        self.llm_matched = 0
        self.new_entities = 0
        self.total = 0

stats = Stats()


# ============================================================
# Stage 1: Rule-based Normalization
# ============================================================

TITLES = ['sir ', 'king ', 'queen ', 'dame ', 'lord ', 'lady ', 'prince ', 'princess ', 'emperor ', 'empress ']
SUFFIXES = [' the great', ' the brave', ' the bold', ' the fair', ' of camelot', ' of the lake',
            ' of cornwall', ' of orkney', ' of britain', ' of ireland', ' de gaul']

def normalize_rule_based(name: str) -> str:
    """규칙 기반 이름 정규화"""
    normalized = name.lower().strip()

    # Remove titles
    for title in TITLES:
        if normalized.startswith(title):
            normalized = normalized[len(title):]
            break

    # Remove suffixes
    for suffix in SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break

    # Remove common patterns
    normalized = re.sub(r'\s+le\s+fay$', '', normalized)
    normalized = re.sub(r'\s+du\s+lac$', '', normalized)

    return normalized.strip()


def try_rule_match(name: str, canonical_map: dict) -> Optional[str]:
    """규칙 정규화 후 canonical map에서 exact match 시도"""
    normalized = normalize_rule_based(name)

    # Direct match
    for canonical_name in canonical_map:
        if normalize_rule_based(canonical_name) == normalized:
            return canonical_name

        # Check aliases
        for alias in canonical_map[canonical_name].get('aliases', []):
            if normalize_rule_based(alias) == normalized:
                return canonical_name

    return None


# ============================================================
# Stage 2: Wikidata QID Matching
# ============================================================

async def search_wikidata(name: str) -> Optional[dict]:
    """Wikidata에서 이름 검색"""
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": 3
    }
    headers = {
        "User-Agent": "Chaldeas/1.0 (https://chaldeas.site; contact@chaldeas.site)"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()

            if data.get("search"):
                result = data["search"][0]
                return {
                    "qid": result["id"],
                    "label": result.get("label", ""),
                    "description": result.get("description", "")
                }
        except Exception as e:
            print(f"    [Wikidata] Error: {e}")

    return None


def try_wikidata_match(qid: str, canonical_map: dict) -> Optional[str]:
    """QID로 canonical map에서 매칭"""
    if not qid:
        return None

    for canonical_name, data in canonical_map.items():
        if data.get('wikidata_qid') == qid:
            return canonical_name

    return None


# ============================================================
# Stage 3: Embedding-based Candidate Search
# ============================================================

def get_embedding_candidates(name: str, limit: int = 30) -> list[dict]:
    """임베딩 유사도로 후보 검색"""
    try:
        from app.services.embeddings import EmbeddingService, VectorStore

        embedding_service = EmbeddingService()
        vector_store = VectorStore()

        # Get embedding
        query_vec = embedding_service.embed_text(name)

        # Search similar
        results = vector_store.search_similar(
            query_vec,
            content_type="person",
            limit=limit,
            min_similarity=0.3
        )

        return results
    except Exception as e:
        print(f"    [Embedding] Error: {e}")
        return []


# ============================================================
# Stage 4: LLM-based Matching
# ============================================================

async def call_openai(prompt: str, model: str = "gpt-5.1-chat-latest") -> str:
    """Call OpenAI API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
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


async def llm_match_with_candidates(
    name: str,
    candidates: list[str],
    category: str
) -> Optional[dict]:
    """후보군 중에서 LLM으로 매칭"""

    if not candidates:
        return None

    category_desc = {
        "arthurian": "Arthurian legends",
        "greek": "Greek mythology/epics",
        "norse": "Norse mythology",
        "celtic": "Celtic/Irish mythology",
        "indian": "Indian epics",
    }

    prompt = f"""You are matching person names from {category_desc.get(category, category)}.

New name: "{name}"

Is this the same person as any of these candidates?
{json.dumps(candidates[:30], ensure_ascii=False, indent=2)}

Rules:
- Match if they refer to the same historical/mythological figure
- Consider spelling variations, translations, epithets
- "Gwalchmai" = "Gawain" (Welsh vs English name for same knight)
- "Chevalier de la Charrette" = "Lancelot" (epithet)

Respond with JSON only:
If match found: {{"match": "ExactCandidateName", "confidence": 0.95, "reason": "brief reason"}}
If no match: {{"match": null, "confidence": 0.0, "reason": "new character"}}
"""

    response = await call_openai(prompt)

    if not response:
        return None

    # Parse response
    try:
        # Extract JSON
        response = response.strip()
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except Exception as e:
        print(f"    [LLM] Parse error: {e}")

    return None


# ============================================================
# Main Pipeline
# ============================================================

async def normalize_single(
    name: str,
    canonical_map: dict,
    category: str,
    book_persons: set = None,
    use_embedding: bool = True,
    use_llm: bool = True
) -> dict:
    """단일 이름 정규화 파이프라인"""

    result = {
        "extracted": name,
        "canonical": None,
        "wikidata_qid": None,
        "confidence": 0.0,
        "method": None
    }

    # Stage 1: Rule-based
    matched = try_rule_match(name, canonical_map)
    if matched:
        result["canonical"] = matched
        result["wikidata_qid"] = canonical_map[matched].get("wikidata_qid")
        result["confidence"] = 0.9
        result["method"] = "rule"
        stats.rule_matched += 1
        return result

    # Stage 2: Wikidata
    wikidata = await search_wikidata(normalize_rule_based(name))
    if wikidata:
        qid = wikidata["qid"]
        matched = try_wikidata_match(qid, canonical_map)
        if matched:
            result["canonical"] = matched
            result["wikidata_qid"] = qid
            result["confidence"] = 0.95
            result["method"] = "wikidata"
            stats.wikidata_matched += 1
            return result
        else:
            # New entity with Wikidata QID
            result["wikidata_qid"] = qid

    # Stage 3: Embedding candidates
    candidates = []
    if use_embedding:
        embedding_results = get_embedding_candidates(name, limit=30)
        candidates = [r.get('content_text', r.get('name', '')) for r in embedding_results if r]
        candidates = [c for c in candidates if c]  # Filter empty

    # Add co-occurrence candidates (same book)
    if book_persons:
        candidates = list(set(candidates) | book_persons)

    # Add category canonical names
    candidates = list(set(candidates) | set(canonical_map.keys()))

    # Stage 4: LLM matching
    if use_llm and candidates:
        llm_result = await llm_match_with_candidates(name, candidates[:30], category)
        if llm_result and llm_result.get("match"):
            matched = llm_result["match"]
            if matched in canonical_map:
                result["canonical"] = matched
                result["wikidata_qid"] = canonical_map[matched].get("wikidata_qid")
                result["confidence"] = llm_result.get("confidence", 0.8)
                result["method"] = "llm"
                stats.llm_matched += 1
                return result

    # New entity
    stats.new_entities += 1
    result["canonical"] = name  # Use extracted name as canonical
    result["confidence"] = 0.5
    result["method"] = "new"

    return result


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
    """Extract unique person names from books"""
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


def load_canonical_map(category: str) -> dict:
    """Load existing canonical map or return empty dict"""
    map_path = CANONICAL_MAPS_DIR / f"{category}.json"
    if map_path.exists():
        try:
            return json.loads(map_path.read_text(encoding='utf-8'))
        except:
            pass
    return {}


async def normalize_category(
    category: str,
    limit: int = 0,
    use_embedding: bool = True,
    use_llm: bool = True
):
    """Normalize all persons in a category"""

    print(f"\n{'='*60}")
    print(f"Entity Normalization v2: {category.upper()}")
    print(f"Stages: Rule → Wikidata → Embedding → LLM")
    print(f"{'='*60}\n")

    # Get books
    books = get_books_by_category(category)
    print(f"Found {len(books)} books in category")

    if not books:
        return

    # Load existing canonical map
    canonical_map = load_canonical_map(category)
    print(f"Existing canonical entities: {len(canonical_map)}")

    # Extract unique persons
    person_to_books = extract_unique_persons(books)
    persons = list(person_to_books.keys())
    print(f"Unique person names to process: {len(persons)}")

    if limit > 0 and limit < len(persons):
        persons = persons[:limit]
        print(f"Limited to first {limit} persons")

    # Extract chunk info
    book_person_chunks = extract_person_chunks(books)

    # Process each person
    all_normalized = []

    for i, name in enumerate(persons):
        stats.total += 1

        if (i + 1) % 20 == 0:
            print(f"\nProgress: {i+1}/{len(persons)} ({100*(i+1)//len(persons)}%)")
            print(f"  Rule: {stats.rule_matched}, Wikidata: {stats.wikidata_matched}, "
                  f"Embedding: {stats.embedding_matched}, LLM: {stats.llm_matched}, New: {stats.new_entities}")

        result = await normalize_single(
            name,
            canonical_map,
            category,
            use_embedding=use_embedding,
            use_llm=use_llm
        )
        all_normalized.append(result)

        # Add to canonical map if new
        canonical = result.get("canonical")
        if canonical and canonical not in canonical_map:
            canonical_map[canonical] = {
                "wikidata_qid": result.get("wikidata_qid"),
                "aliases": [],
                "confidence": result.get("confidence", 0.5)
            }

        # Add alias
        if canonical and result["extracted"] != canonical:
            if result["extracted"] not in canonical_map[canonical].get("aliases", []):
                canonical_map[canonical].setdefault("aliases", []).append(result["extracted"])

        # Rate limit for Wikidata
        await asyncio.sleep(0.1)

    # Save canonical map
    map_path = CANONICAL_MAPS_DIR / f"{category}.json"
    with open(map_path, 'w', encoding='utf-8') as f:
        json.dump(canonical_map, f, ensure_ascii=False, indent=2)
    print(f"\nSaved canonical map to {map_path}")

    # Build book-persons relationships
    book_persons_data = []

    extracted_to_result = {r["extracted"]: r for r in all_normalized}

    for book_id, person_chunks in book_person_chunks.items():
        for extracted_name, chunk_ids in person_chunks.items():
            result = extracted_to_result.get(extracted_name, {})
            book_persons_data.append({
                "book_id": book_id,
                "extracted_name": extracted_name,
                "canonical_name": result.get("canonical"),
                "wikidata_qid": result.get("wikidata_qid"),
                "chunk_ids": sorted(set(chunk_ids)),
                "mention_count": len(chunk_ids)
            })

    # Save book-persons
    bp_path = OUTPUT_DIR / f"{category}_book_persons.json"
    with open(bp_path, 'w', encoding='utf-8') as f:
        json.dump(book_persons_data, f, ensure_ascii=False, indent=2)
    print(f"Saved book-persons to {bp_path}")

    # Final summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total processed: {stats.total}")
    print(f"  Rule matched:     {stats.rule_matched} ({100*stats.rule_matched//max(1,stats.total)}%)")
    print(f"  Wikidata matched: {stats.wikidata_matched} ({100*stats.wikidata_matched//max(1,stats.total)}%)")
    print(f"  Embedding matched:{stats.embedding_matched} ({100*stats.embedding_matched//max(1,stats.total)}%)")
    print(f"  LLM matched:      {stats.llm_matched} ({100*stats.llm_matched//max(1,stats.total)}%)")
    print(f"  New entities:     {stats.new_entities} ({100*stats.new_entities//max(1,stats.total)}%)")
    print(f"\nCanonical entities: {len(canonical_map)}")
    print(f"Book-person relationships: {len(book_persons_data)}")


async def main():
    parser = argparse.ArgumentParser(description="Entity Normalization v2")
    parser.add_argument("--category", type=str, default="arthurian",
                        choices=list(CATEGORY_KEYWORDS.keys()))
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit persons to process (0 = all)")
    parser.add_argument("--no-embedding", action="store_true",
                        help="Skip embedding search")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM matching")
    parser.add_argument("--list-categories", action="store_true")

    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for cat, keywords in CATEGORY_KEYWORDS.items():
            books = get_books_by_category(cat)
            print(f"  {cat}: {len(books)} books")
        return

    await normalize_category(
        args.category,
        args.limit,
        use_embedding=not args.no_embedding,
        use_llm=not args.no_llm
    )


if __name__ == "__main__":
    asyncio.run(main())
