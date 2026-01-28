"""
Wikidata Matching for DB Persons

Matches our DB persons against Wikidata entities:
1. Search Wikidata by person name
2. Fetch candidate data (aliases, dates, description)
3. Run matching pipeline (fuzzy + embedding + LLM)
4. Save results with wikidata_id

Usage:
    python poc/scripts/wikidata_match_persons.py --limit 100
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import time
import argparse
import requests
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import func
from app.db.session import SessionLocal
from app.models.person import Person
from app.models.event import Event
from app.models.associations import event_persons


def flush_print(*args, **kwargs):
    """Print with immediate flush"""
    print(*args, **kwargs)
    sys.stdout.flush()


@dataclass
class WikidataCandidate:
    qid: str
    name: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    birth_year: Optional[int] = None
    death_year: Optional[int] = None


@dataclass
class MatchResult:
    person_id: int
    person_name: str
    person_birth: Optional[int]
    person_death: Optional[int]
    wikidata_qid: Optional[str] = None
    wikidata_name: Optional[str] = None
    match_confidence: float = 0.0
    match_method: str = "none"
    aliases_found: list[str] = field(default_factory=list)
    error: Optional[str] = None


# ============================================================
# Wikidata Search
# ============================================================

def search_wikidata(name: str, limit: int = 5) -> list[dict]:
    """Search Wikidata for entities by name"""
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "limit": limit,
        "format": "json",
    }
    headers = {"User-Agent": "CHALDEAS/1.0"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("search", [])
    except Exception as e:
        flush_print(f"    Search error: {e}")
        return []


def fetch_wikidata_entity(qid: str) -> Optional[WikidataCandidate]:
    """Fetch detailed entity data from Wikidata"""
    query = """
    SELECT ?label ?description ?birthYear ?deathYear WHERE {
        wd:%s rdfs:label ?label . FILTER(LANG(?label) = "en")
        OPTIONAL { wd:%s schema:description ?description . FILTER(LANG(?description) = "en") }
        OPTIONAL { wd:%s wdt:P569 ?birth . BIND(YEAR(?birth) AS ?birthYear) }
        OPTIONAL { wd:%s wdt:P570 ?death . BIND(YEAR(?death) AS ?deathYear) }
    }
    LIMIT 1
    """ % (qid, qid, qid, qid)

    url = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/json", "User-Agent": "CHALDEAS/1.0"}

    try:
        response = requests.get(url, params={"query": query}, headers=headers, timeout=15)
        response.raise_for_status()
        results = response.json()["results"]["bindings"]

        if not results:
            return None

        r = results[0]
        candidate = WikidataCandidate(
            qid=qid,
            name=r.get("label", {}).get("value", ""),
            description=r.get("description", {}).get("value", ""),
            birth_year=int(r["birthYear"]["value"]) if "birthYear" in r else None,
            death_year=int(r["deathYear"]["value"]) if "deathYear" in r else None,
        )

        # Fetch aliases
        candidate.aliases = fetch_aliases(qid)
        return candidate

    except Exception as e:
        flush_print(f"    Fetch error for {qid}: {e}")
        return None


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

    try:
        response = requests.get(url, params={"query": query}, headers=headers, timeout=10)
        response.raise_for_status()
        results = response.json()["results"]["bindings"]
        return [r["alias"]["value"] for r in results]
    except:
        return []


# ============================================================
# Matching Logic
# ============================================================

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def fuzzy_match(name1: str, name2: str) -> dict:
    from rapidfuzz import fuzz
    from rapidfuzz.distance import JaroWinkler

    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    return {
        "ratio": fuzz.ratio(n1, n2) / 100,
        "token_set": fuzz.token_set_ratio(n1, n2) / 100,
        "jaro_winkler": JaroWinkler.similarity(n1, n2),
    }


def embedding_similarity(text1: str, text2: str) -> float:
    import numpy as np
    model = get_embedding_model()
    emb1 = model.encode(text1, normalize_embeddings=True)
    emb2 = model.encode(text2, normalize_embeddings=True)
    return float(np.dot(emb1, emb2))


def verify_with_llm(person_name: str, person_birth: int, person_death: int,
                    candidate: WikidataCandidate) -> dict:
    """Verify match using local Ollama"""

    # Format lifespans
    def fmt_year(y):
        if y is None:
            return "unknown"
        return f"{abs(y)} BCE" if y < 0 else str(y)

    person_lifespan = f"{fmt_year(person_birth)} - {fmt_year(person_death)}"
    candidate_lifespan = f"{fmt_year(candidate.birth_year)} - {fmt_year(candidate.death_year)}"

    prompt = f"""Determine if these two refer to the SAME historical person.

Person A (our database):
- Name: "{person_name}"
- Lifespan: {person_lifespan}

Person B (Wikidata candidate):
- Name: "{candidate.name}"
- Description: "{candidate.description}"
- Lifespan: {candidate_lifespan}
- Aliases: {', '.join(candidate.aliases[:5]) if candidate.aliases else 'none'}

Respond ONLY with valid JSON:
{{"decision": "SAME" or "DIFFERENT", "confidence": 0.0-1.0, "reason": "brief"}}"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma2:9b-instruct-q4_0",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=60
        )
        response.raise_for_status()
        result_text = response.json()["response"]

        import re
        json_match = re.search(r'\{[^}]+\}', result_text)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        pass

    return {"decision": "UNCERTAIN", "confidence": 0.0, "reason": str(e) if 'e' in dir() else "error"}


def match_person_to_wikidata(person: Person) -> MatchResult:
    """Full matching pipeline for one person"""

    result = MatchResult(
        person_id=person.id,
        person_name=person.name,
        person_birth=person.birth_year,
        person_death=person.death_year,
    )

    # Step 1: Search Wikidata
    search_results = search_wikidata(person.name)
    if not search_results:
        result.error = "No Wikidata results"
        return result

    time.sleep(0.5)  # Rate limiting

    # Step 2: Check top candidates
    best_match = None
    best_score = 0.0
    best_method = "none"

    for sr in search_results[:3]:  # Check top 3
        qid = sr["id"]
        candidate = fetch_wikidata_entity(qid)
        if not candidate:
            continue

        time.sleep(0.3)  # Rate limiting

        # Exact match
        if person.name.lower() == candidate.name.lower():
            best_match = candidate
            best_score = 1.0
            best_method = "exact"
            break

        # Alias match
        if person.name.lower() in [a.lower() for a in candidate.aliases]:
            best_match = candidate
            best_score = 0.95
            best_method = "alias"
            break

        # Fuzzy + Embedding
        fuzzy = fuzzy_match(person.name, candidate.name)
        fuzzy_score = fuzzy["jaro_winkler"] * 0.4 + fuzzy["token_set"] * 0.3 + fuzzy["ratio"] * 0.3
        emb_score = embedding_similarity(person.name, candidate.name)
        combined = fuzzy_score * 0.4 + emb_score * 0.6

        # Date matching bonus/penalty
        if person.birth_year and candidate.birth_year:
            year_diff = abs(person.birth_year - candidate.birth_year)
            if year_diff <= 5:
                combined *= 1.2  # Bonus
            elif year_diff > 100:
                combined *= 0.5  # Penalty

        if combined > best_score:
            best_score = combined
            best_match = candidate
            best_method = "fuzzy_emb"

    if not best_match:
        result.error = "No good candidates"
        return result

    # Step 3: LLM verification for uncertain matches
    if best_method == "fuzzy_emb" and best_score >= 0.5:
        flush_print(f"    LLM verifying: {person.name} vs {best_match.name}...")
        llm_result = verify_with_llm(person.name, person.birth_year, person.death_year, best_match)

        if llm_result["decision"] == "SAME" and llm_result["confidence"] >= 0.8:
            best_score = best_score * 0.3 + llm_result["confidence"] * 0.7
            best_method = "llm_verified"
        elif llm_result["decision"] == "DIFFERENT":
            best_score = 0.0
            best_method = "llm_rejected"

    # Final decision
    if best_score >= 0.7:
        result.wikidata_qid = best_match.qid
        result.wikidata_name = best_match.name
        result.match_confidence = min(best_score, 1.0)
        result.match_method = best_method
        result.aliases_found = best_match.aliases
    else:
        result.error = f"Low confidence: {best_score:.2f}"

    return result


# ============================================================
# Main
# ============================================================

def get_sample_persons(db, limit: int) -> list[Person]:
    """Get sample persons prioritized by event count"""

    # Get persons with most events
    subq = (
        db.query(event_persons.c.person_id, func.count().label('event_count'))
        .group_by(event_persons.c.person_id)
        .subquery()
    )

    persons = (
        db.query(Person)
        .outerjoin(subq, Person.id == subq.c.person_id)
        .filter(Person.wikidata_id.is_(None))  # Only ones without wikidata_id
        .order_by(subq.c.event_count.desc().nullslast())
        .limit(limit)
        .all()
    )

    return persons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM verification")
    args = parser.parse_args()

    flush_print("="*60)
    flush_print("Wikidata Matching for DB Persons")
    flush_print("="*60)

    # Load embedding model first
    flush_print("Loading embedding model...")
    get_embedding_model()
    flush_print("Model loaded!")

    db = SessionLocal()
    try:
        persons = get_sample_persons(db, args.limit)
        flush_print(f"\nProcessing {len(persons)} persons...")

        results = []
        matched = 0

        for i, person in enumerate(persons):
            lifespan = f" ({person.birth_year}-{person.death_year or '?'})" if person.birth_year else ""
            flush_print(f"\n[{i+1}/{len(persons)}] {person.name}{lifespan}")

            result = match_person_to_wikidata(person)
            results.append(result)

            if result.wikidata_qid:
                matched += 1
                flush_print(f"    MATCHED: {result.wikidata_qid} ({result.match_method}, {result.match_confidence:.2f})")
                flush_print(f"    Aliases: {len(result.aliases_found)}")
            else:
                flush_print(f"    NO MATCH: {result.error}")

            # Progress save every 20
            if (i + 1) % 20 == 0:
                save_results(results)

        # Final save
        save_results(results)

        flush_print("\n" + "="*60)
        flush_print("SUMMARY")
        flush_print("="*60)
        flush_print(f"Total processed: {len(results)}")
        flush_print(f"Matched: {matched} ({matched/len(results)*100:.1f}%)")
        flush_print(f"Not matched: {len(results) - matched}")

        # Breakdown by method
        methods = {}
        for r in results:
            methods[r.match_method] = methods.get(r.match_method, 0) + 1
        flush_print("\nBy method:")
        for m, c in sorted(methods.items(), key=lambda x: -x[1]):
            flush_print(f"  {m}: {c}")

    finally:
        db.close()


def save_results(results: list[MatchResult]):
    output_path = Path(__file__).parent.parent / "data" / "wikidata_match_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "count": len(results),
            "results": [asdict(r) for r in results]
        }, f, indent=2, ensure_ascii=False)

    flush_print(f"    [Saved to {output_path}]")


if __name__ == "__main__":
    main()
