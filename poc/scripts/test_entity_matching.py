"""
Entity Matching Pipeline Test

Tests the full entity matching pipeline with Joan of Arc and Alexander the Great:
1. Fetch Wikidata (aliases, descriptions, dates)
2. Build alias table
3. Fuzzy matching (trigram, Jaro-Winkler)
4. Embedding matching (sentence-transformers)
5. LLM verification (gemma2:9b via Ollama)

Usage:
    python poc/scripts/test_entity_matching.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# Wikidata IDs
ENTITIES = {
    "alexander": "Q8409",   # Alexander the Great
    "joan": "Q7226",        # Joan of Arc
}


@dataclass
class WikidataEntity:
    """Entity data from Wikidata"""
    qid: str
    name: str
    description: str
    aliases: list[str] = field(default_factory=list)
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    occupation: Optional[str] = None


def fetch_wikidata(qid: str) -> WikidataEntity:
    """Fetch entity data from Wikidata SPARQL endpoint"""

    # Main entity query
    query = """
    SELECT ?label ?description ?birthYear ?deathYear ?occupationLabel WHERE {
        wd:%s rdfs:label ?label .
        FILTER(LANG(?label) = "en")

        OPTIONAL { wd:%s schema:description ?description . FILTER(LANG(?description) = "en") }
        OPTIONAL {
            wd:%s wdt:P569 ?birthDate .
            BIND(YEAR(?birthDate) AS ?birthYear)
        }
        OPTIONAL {
            wd:%s wdt:P570 ?deathDate .
            BIND(YEAR(?deathDate) AS ?deathYear)
        }
        OPTIONAL {
            wd:%s wdt:P106 ?occupation .
            ?occupation rdfs:label ?occupationLabel .
            FILTER(LANG(?occupationLabel) = "en")
        }
    }
    LIMIT 1
    """ % (qid, qid, qid, qid, qid)

    url = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/json", "User-Agent": "CHALDEAS/1.0"}

    response = requests.get(url, params={"query": query}, headers=headers)
    response.raise_for_status()
    results = response.json()["results"]["bindings"]

    if not results:
        raise ValueError(f"No data found for {qid}")

    r = results[0]

    # Parse birth/death years (handle BCE)
    birth_year = None
    death_year = None
    if "birthYear" in r:
        birth_year = int(r["birthYear"]["value"])
    if "deathYear" in r:
        death_year = int(r["deathYear"]["value"])

    entity = WikidataEntity(
        qid=qid,
        name=r["label"]["value"],
        description=r.get("description", {}).get("value", ""),
        birth_year=birth_year,
        death_year=death_year,
        occupation=r.get("occupationLabel", {}).get("value"),
    )

    # Fetch aliases separately
    entity.aliases = fetch_aliases(qid)

    return entity


def fetch_aliases(qid: str) -> list[str]:
    """Fetch English aliases from Wikidata"""

    query = """
    SELECT ?alias WHERE {
        wd:%s skos:altLabel ?alias .
        FILTER(LANG(?alias) = "en")
    }
    """ % qid

    url = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/json", "User-Agent": "CHALDEAS/1.0"}

    response = requests.get(url, params={"query": query}, headers=headers)
    response.raise_for_status()
    results = response.json()["results"]["bindings"]

    return [r["alias"]["value"] for r in results]


def print_entity(entity: WikidataEntity):
    """Pretty print entity data"""
    print(f"\n{'='*60}")
    print(f"Entity: {entity.name} ({entity.qid})")
    print(f"{'='*60}")
    print(f"Description: {entity.description}")

    if entity.birth_year and entity.death_year:
        birth = f"{abs(entity.birth_year)} BCE" if entity.birth_year < 0 else str(entity.birth_year)
        death = f"{abs(entity.death_year)} BCE" if entity.death_year < 0 else str(entity.death_year)
        print(f"Lifespan: {birth} - {death}")

    if entity.occupation:
        print(f"Occupation: {entity.occupation}")

    print(f"\nAliases ({len(entity.aliases)}):")
    for alias in sorted(entity.aliases):
        print(f"  - {alias}")


# ============================================================
# Stage 2: Fuzzy Matching
# ============================================================

def fuzzy_match(name1: str, name2: str) -> dict:
    """Calculate fuzzy similarity scores"""
    try:
        from rapidfuzz import fuzz
        from rapidfuzz.distance import JaroWinkler
    except ImportError:
        print("Installing rapidfuzz...")
        import subprocess
        subprocess.check_call(["pip", "install", "rapidfuzz"])
        from rapidfuzz import fuzz
        from rapidfuzz.distance import JaroWinkler

    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    return {
        "ratio": fuzz.ratio(n1, n2) / 100,
        "partial_ratio": fuzz.partial_ratio(n1, n2) / 100,
        "token_sort": fuzz.token_sort_ratio(n1, n2) / 100,
        "token_set": fuzz.token_set_ratio(n1, n2) / 100,
        "jaro_winkler": JaroWinkler.similarity(n1, n2),
    }


def combined_fuzzy_score(scores: dict) -> float:
    """Weighted combination of fuzzy scores"""
    return (
        scores["jaro_winkler"] * 0.3 +
        scores["token_set"] * 0.4 +
        scores["ratio"] * 0.3
    )


# ============================================================
# Stage 3: Embedding Matching
# ============================================================

_embedding_model = None

def get_embedding_model():
    """Lazy load sentence-transformers model"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("Installing sentence-transformers...")
            import subprocess
            subprocess.check_call(["pip", "install", "sentence-transformers"])
            from sentence_transformers import SentenceTransformer

        print("Loading embedding model (all-MiniLM-L6-v2)...")
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def get_embedding(text: str):
    """Get embedding vector"""
    import numpy as np
    model = get_embedding_model()
    return model.encode(text, normalize_embeddings=True)


def embedding_similarity(text1: str, text2: str) -> float:
    """Calculate cosine similarity between embeddings"""
    import numpy as np
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)
    return float(np.dot(emb1, emb2))


# ============================================================
# Stage 4: LLM Verification (Ollama gemma2:9b)
# ============================================================

def verify_with_llm(
    extracted_name: str,
    extracted_context: str,
    db_name: str,
    db_description: str,
    db_lifespan: str
) -> dict:
    """Verify entity match using local Ollama model"""

    prompt = f"""Determine if these two historical entities refer to the same person.

Entity A (extracted from document):
- Name: "{extracted_name}"
- Context: "{extracted_context}"

Entity B (database candidate):
- Name: "{db_name}"
- Description: "{db_description}"
- Lifespan: {db_lifespan}

Respond ONLY with valid JSON (no markdown, no explanation):
{{"decision": "SAME" or "DIFFERENT" or "UNCERTAIN", "confidence": 0.0-1.0, "reason": "brief explanation"}}"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma2:9b-instruct-q4_0",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=120
        )
        response.raise_for_status()
        result_text = response.json()["response"]

        # Parse JSON from response
        import re
        json_match = re.search(r'\{[^}]+\}', result_text)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {"decision": "UNCERTAIN", "confidence": 0.5, "reason": "Failed to parse LLM response"}

    except requests.exceptions.ConnectionError:
        return {"decision": "UNCERTAIN", "confidence": 0.0, "reason": "Ollama not running"}
    except Exception as e:
        return {"decision": "UNCERTAIN", "confidence": 0.0, "reason": str(e)}


# ============================================================
# Full Pipeline Test
# ============================================================

def test_matching(entity: WikidataEntity, test_names: list[str]):
    """Test matching pipeline with various name variations"""

    print(f"\n{'='*60}")
    print(f"Testing matches against: {entity.name}")
    print(f"{'='*60}")

    # Prepare DB entity info
    birth = f"{abs(entity.birth_year)} BCE" if entity.birth_year and entity.birth_year < 0 else str(entity.birth_year or "?")
    death = f"{abs(entity.death_year)} BCE" if entity.death_year and entity.death_year < 0 else str(entity.death_year or "?")
    db_lifespan = f"{birth} - {death}"

    results = []

    for test_name in test_names:
        print(f"\n--- Testing: '{test_name}' ---")

        # Stage 1: Exact match
        exact_match = test_name.lower() == entity.name.lower()
        alias_match = test_name.lower() in [a.lower() for a in entity.aliases]

        if exact_match:
            print(f"  [EXACT MATCH] Confidence: 1.0")
            results.append({"name": test_name, "match": True, "confidence": 1.0, "method": "exact"})
            continue

        if alias_match:
            print(f"  [ALIAS MATCH] Confidence: 0.95")
            results.append({"name": test_name, "match": True, "confidence": 0.95, "method": "alias"})
            continue

        # Stage 2: Fuzzy matching
        fuzzy_scores = fuzzy_match(test_name, entity.name)
        fuzzy_combined = combined_fuzzy_score(fuzzy_scores)
        print(f"  Fuzzy Score: {fuzzy_combined:.3f}")
        print(f"    - Jaro-Winkler: {fuzzy_scores['jaro_winkler']:.3f}")
        print(f"    - Token Set: {fuzzy_scores['token_set']:.3f}")

        # Stage 3: Embedding similarity
        emb_sim = embedding_similarity(test_name, entity.name)
        print(f"  Embedding Similarity: {emb_sim:.3f}")

        # Combined score (before LLM)
        combined = fuzzy_combined * 0.4 + emb_sim * 0.6
        print(f"  Combined Score: {combined:.3f}")

        # Stage 4: LLM verification (if score >= 0.6)
        if combined >= 0.6:
            print(f"  [LLM VERIFY] Calling gemma2:9b...")
            llm_result = verify_with_llm(
                extracted_name=test_name,
                extracted_context=f"Historical figure known as {test_name}",
                db_name=entity.name,
                db_description=entity.description,
                db_lifespan=db_lifespan
            )
            print(f"    Decision: {llm_result['decision']}")
            print(f"    Confidence: {llm_result['confidence']}")
            print(f"    Reason: {llm_result['reason']}")

            if llm_result["decision"] == "SAME" and llm_result["confidence"] >= 0.8:
                final_confidence = combined * 0.3 + llm_result["confidence"] * 0.7
                results.append({"name": test_name, "match": True, "confidence": final_confidence, "method": "llm_verified"})
            else:
                results.append({"name": test_name, "match": False, "confidence": combined, "method": "llm_rejected"})
        else:
            results.append({"name": test_name, "match": False, "confidence": combined, "method": "low_score"})

    return results


def main():
    print("="*60)
    print("CHALDEAS Entity Matching Pipeline Test")
    print("="*60)

    # Step 1: Fetch Wikidata
    print("\n[STEP 1] Fetching Wikidata...")
    entities = {}

    for key, qid in ENTITIES.items():
        print(f"  Fetching {qid}...")
        try:
            entities[key] = fetch_wikidata(qid)
            print_entity(entities[key])
        except Exception as e:
            print(f"  ERROR: {e}")
            return
        time.sleep(1)  # Rate limiting

    # Step 2: Test matching with various name variations
    print("\n[STEP 2] Loading embedding model...")
    get_embedding_model()  # Pre-load

    print("\n[STEP 3] Testing Entity Matching Pipeline...")

    # Test Alexander variations
    alexander_tests = [
        "Alexander the Great",           # exact
        "Alexander III of Macedon",      # alias (should be in Wikidata)
        "Iskandar",                       # alias (Arabic)
        "Alexandros",                     # alias (Greek)
        "Alexander",                      # partial
        "The Great Alexander",            # reordered
        "Alexander of Macedonia",         # variation
        "King Alexander",                 # with title
        "Alexander VI",                   # DIFFERENT PERSON (Pope)
        "Alexandr Veliký",                # Czech (different language)
    ]

    alexander_results = test_matching(entities["alexander"], alexander_tests)

    # Test Joan of Arc variations
    joan_tests = [
        "Joan of Arc",                    # exact
        "Jeanne d'Arc",                   # alias (French)
        "The Maid of Orléans",            # alias
        "Saint Joan",                     # alias
        "Joan",                           # partial
        "Joanne of Arc",                  # typo
        "Joan the Maid",                  # variation
        "Pope Joan",                      # DIFFERENT PERSON
    ]

    joan_results = test_matching(entities["joan"], joan_tests)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    print("\nAlexander the Great matches:")
    for r in alexander_results:
        status = "MATCH" if r["match"] else "NO MATCH"
        print(f"  [{status}] {r['name']}: {r['confidence']:.2f} ({r['method']})")

    print("\nJoan of Arc matches:")
    for r in joan_results:
        status = "MATCH" if r["match"] else "NO MATCH"
        print(f"  [{status}] {r['name']}: {r['confidence']:.2f} ({r['method']})")

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "entity_matching_test_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "entities": {
                "alexander": {
                    "qid": entities["alexander"].qid,
                    "name": entities["alexander"].name,
                    "aliases": entities["alexander"].aliases,
                },
                "joan": {
                    "qid": entities["joan"].qid,
                    "name": entities["joan"].name,
                    "aliases": entities["joan"].aliases,
                }
            },
            "results": {
                "alexander": alexander_results,
                "joan": joan_results
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
