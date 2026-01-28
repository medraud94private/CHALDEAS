"""
Wikidata Entity Matching using Reconciliation API

The reconciliation API is designed for bulk entity matching and has better rate limits.
https://wikidata.reconci.link/

Usage:
    python poc/scripts/wikidata_reconcile.py --batch-size 50 --limit 1000
    python poc/scripts/wikidata_reconcile.py --resume
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import time
import argparse
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import requests

RECONCILE_API = "https://wikidata.reconci.link/en/api"
# New checkpoint system: index (small) + results (append-only JSONL)
INDEX_FILE = Path(__file__).parent.parent / "data" / "reconcile_index.json"
RESULTS_JSONL = Path(__file__).parent.parent / "data" / "reconcile_results.jsonl"
# Legacy files for backward compatibility
CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "reconcile_checkpoint.json"
RESULTS_FILE = Path(__file__).parent.parent / "data" / "reconcile_results.json"


def extract_years_from_description(desc: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract birth and death years from description like '(1879–1955)' or '(1642-1727)'"""
    if not desc:
        return None, None

    # Pattern for year ranges: (YYYY–YYYY), (YYYY-YYYY), (YYYY–), (-YYYY)
    # Also handle BCE dates
    patterns = [
        r'\((\d{3,4})[\–\-](\d{3,4})\)',  # (1879-1955)
        r'\((\d{3,4})[\–\-]\)',  # (1879-)  still alive
        r'\([\–\-](\d{3,4})\)',  # (-1955)  unknown birth
        r'\((\d{3,4})\?[\–\-](\d{3,4})\?\)',  # (1642?-1727?)
    ]

    for pattern in patterns:
        match = re.search(pattern, desc)
        if match:
            groups = match.groups()
            birth = int(groups[0]) if groups[0] else None
            death = int(groups[1]) if len(groups) > 1 and groups[1] else None
            return birth, death

    return None, None


def calculate_lifespan_match(
    person_birth: Optional[int],
    person_death: Optional[int],
    wiki_birth: Optional[int],
    wiki_death: Optional[int],
    tolerance: int = 3
) -> Tuple[float, str]:
    """Calculate lifespan match score"""
    if person_birth is None and person_death is None:
        return 0.5, "no_person_dates"
    if wiki_birth is None and wiki_death is None:
        return 0.5, "no_wiki_dates"

    birth_match = None
    death_match = None

    if person_birth and wiki_birth:
        birth_match = abs(person_birth - wiki_birth) <= tolerance
    if person_death and wiki_death:
        death_match = abs(person_death - wiki_death) <= tolerance

    if birth_match is True and death_match is True:
        return 1.0, "both_match"
    elif birth_match is True and death_match is None:
        return 0.8, "birth_match_only"
    elif birth_match is None and death_match is True:
        return 0.8, "death_match_only"
    elif birth_match is True and death_match is False:
        return 0.3, "birth_match_death_mismatch"
    elif birth_match is False and death_match is True:
        return 0.3, "birth_mismatch_death_match"
    elif birth_match is False and death_match is False:
        return 0.0, "both_mismatch"
    elif birth_match is False:
        return 0.2, "birth_mismatch"
    elif death_match is False:
        return 0.2, "death_mismatch"

    return 0.5, "partial_data"


def reconcile_batch(persons: List[Dict], delay: float = 1.0) -> Dict:
    """
    Send batch query to reconciliation API.

    persons: list of {"id": person_id, "name": name, "birth_year": int, "death_year": int}
    Returns: dict of person_id -> match result
    """
    # Build queries
    queries = {}
    for p in persons:
        queries[f"q{p['id']}"] = {
            "query": p["name"],
            "type": "Q5",  # human
            "limit": 5
        }

    try:
        resp = requests.post(
            RECONCILE_API,
            data={"queries": json.dumps(queries)},
            headers={"User-Agent": "CHALDEAS/1.0"},
            timeout=60
        )

        if resp.status_code != 200:
            print(f"  [WARN] API returned {resp.status_code}")
            return {}

        results = resp.json()

    except Exception as e:
        print(f"  [ERROR] API error: {e}")
        return {}

    # Process results
    matched = {}
    for p in persons:
        key = f"q{p['id']}"
        if key not in results:
            continue

        candidates = results[key].get("result", [])
        if not candidates:
            matched[p["id"]] = {"match_type": "no_match", "confidence": 0}
            continue

        # Find best match considering lifespan
        best_match = None
        best_score = 0

        for c in candidates:
            wiki_birth, wiki_death = extract_years_from_description(c.get("description", ""))

            lifespan_score, lifespan_reason = calculate_lifespan_match(
                p.get("birth_year"), p.get("death_year"),
                wiki_birth, wiki_death
            )

            # Combine name score (from API) with lifespan score
            name_score = c.get("score", 0) / 100.0

            # If lifespan clearly mismatches, reject
            if lifespan_score == 0.0:
                continue

            # Calculate combined score
            if lifespan_score >= 0.8:
                combined = name_score * 1.0  # Trust name score
            elif lifespan_score >= 0.5:
                combined = name_score * 0.9
            else:
                combined = name_score * 0.5

            if combined > best_score:
                best_score = combined
                best_match = {
                    "qid": c["id"],
                    "name": c.get("name", ""),
                    "description": c.get("description", ""),
                    "name_score": name_score,
                    "lifespan_score": lifespan_score,
                    "lifespan_reason": lifespan_reason,
                    "combined_score": combined,
                    "api_match": c.get("match", False)
                }

        if best_match and best_score >= 0.8:
            matched[p["id"]] = {
                "match_type": "matched",
                "confidence": best_score,
                **best_match
            }
        elif best_match and best_score >= 0.5:
            matched[p["id"]] = {
                "match_type": "uncertain",
                "confidence": best_score,
                **best_match
            }
        else:
            matched[p["id"]] = {
                "match_type": "no_match",
                "confidence": best_score if best_match else 0
            }

    time.sleep(delay)
    return matched


def load_persons(limit: int, offset: int = 0) -> List[Dict]:
    """Load persons from DB - optimized to only fetch required columns"""
    from app.db.session import SessionLocal
    from app.models.person import Person

    db = SessionLocal()
    try:
        # Only select the columns we need for matching
        query = db.query(
            Person.id,
            Person.name,
            Person.birth_year,
            Person.death_year
        ).filter(
            Person.wikidata_id.is_(None)
        ).order_by(Person.id).offset(offset).limit(limit)

        persons = []
        for row in query:
            persons.append({
                "id": row.id,
                "name": row.name,
                "birth_year": row.birth_year,
                "death_year": row.death_year
            })
        return persons
    finally:
        db.close()


def load_index() -> Optional[Dict]:
    """Load index file (small, contains only offset and stats)"""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_index(stats: Dict, offset: int):
    """Save index file atomically"""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "last_offset": offset,
        "stats": stats
    }

    # Write atomically
    temp_path = INDEX_FILE.with_suffix('.tmp')
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    temp_path.replace(INDEX_FILE)


def append_results(results: List[Dict]):
    """Append results to JSONL file (one JSON per line)"""
    RESULTS_JSONL.parent.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_JSONL, "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def save_checkpoint(results: List[Dict], stats: Dict, offset: int):
    """Save checkpoint - append results to JSONL and update index"""
    append_results(results)
    save_index(stats, offset)
    print(f"  [Checkpoint saved: {len(results)} new results, offset {offset}]")


def load_checkpoint() -> Optional[Dict]:
    """Load checkpoint - for backward compatibility, just returns index info"""
    return load_index()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=25, help="Queries per API call")
    parser.add_argument("--limit", type=int, default=1000, help="Total persons to process")
    parser.add_argument("--offset", type=int, default=0, help="Starting offset")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between batches (seconds)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--checkpoint-interval", type=int, default=100, help="Save checkpoint every N results")
    args = parser.parse_args()

    # Handle resume - now just loads the index (small file)
    if args.resume:
        index = load_index()
        if index:
            args.offset = index["last_offset"]
            print(f"Resuming from checkpoint: offset {args.offset}")
            print(f"Previous stats: {index.get('stats', {})}")
        else:
            print("No checkpoint found, starting fresh")

    print(f"=== Wikidata Reconciliation Matching ===")
    print(f"Batch size: {args.batch_size}, Limit: {args.limit}, Delay: {args.delay}s")
    print(f"Offset: {args.offset}")

    # Load persons
    print("Loading persons from DB...")
    persons = load_persons(args.limit, args.offset)
    print(f"Loaded {len(persons)} persons")

    if not persons:
        print("No persons to process")
        return

    # Stats for this run
    stats = {
        "total": len(persons),
        "matched": 0,
        "uncertain": 0,
        "no_match": 0,
        "errors": 0
    }

    start_time = time.time()
    processed = 0
    batch_results = []  # Accumulate results for current checkpoint interval

    # Process in batches
    for i in range(0, len(persons), args.batch_size):
        batch = persons[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(persons) + args.batch_size - 1) // args.batch_size

        print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(batch)} persons...")

        results = reconcile_batch(batch, args.delay)

        for p in batch:
            result = results.get(p["id"], {"match_type": "error"})
            result["person_id"] = p["id"]
            result["person_name"] = p["name"]
            batch_results.append(result)

            match_type = result.get("match_type", "error")
            if match_type == "matched":
                stats["matched"] += 1
                qid = result.get("qid", "?")
                conf = result.get("confidence", 0)
                print(f"  {p['name']} -> {qid} ({conf:.2f})")
            elif match_type == "uncertain":
                stats["uncertain"] += 1
                print(f"  {p['name']} -> uncertain ({result.get('confidence', 0):.2f})")
            elif match_type == "no_match":
                stats["no_match"] += 1
            else:
                stats["errors"] += 1

            processed += 1

        # Checkpoint - save accumulated batch results and update index
        if processed % args.checkpoint_interval < args.batch_size:
            save_checkpoint(batch_results, stats, args.offset + processed)
            batch_results = []  # Clear after saving

    # Save any remaining results
    if batch_results:
        save_checkpoint(batch_results, stats, args.offset + processed)

    elapsed = time.time() - start_time

    # Summary
    print(f"\n=== Results ===")
    print(f"Time: {elapsed:.1f}s ({elapsed/len(persons):.2f}s per person)")
    print(f"Total: {stats['total']}")
    print(f"Matched: {stats['matched']} ({100*stats['matched']/stats['total']:.1f}%)")
    print(f"Uncertain: {stats['uncertain']}")
    print(f"No match: {stats['no_match']}")
    print(f"Errors: {stats['errors']}")

    print(f"\nResults saved to: {RESULTS_JSONL}")
    print(f"Index saved to: {INDEX_FILE}")


if __name__ == "__main__":
    main()
