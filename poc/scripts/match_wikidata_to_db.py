"""
Match Wikidata persons to our DB (Reverse Approach)

Takes fetched Wikidata persons and matches them to existing DB records.
Also prepares Wikipedia sources for import.

Usage:
    python poc/scripts/match_wikidata_to_db.py --input poc/data/wikidata_philosophers.json
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from app.models.person import Person


@dataclass
class MatchResult:
    wikidata_qid: str
    wikidata_name: str
    wikidata_birth: Optional[int]
    wikidata_death: Optional[int]
    db_person_id: Optional[int]
    db_person_name: Optional[str]
    match_score: float
    match_type: str  # exact, fuzzy, lifespan, new
    wikipedia_url: Optional[str] = None


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    # Lowercase, remove extra spaces
    name = " ".join(name.lower().split())
    # Remove common suffixes/prefixes
    for suffix in [" the great", " the elder", " the younger", " i", " ii", " iii", " iv", " v"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name


def name_similarity(name1: str, name2: str) -> float:
    """Calculate name similarity (0-100)."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if n1 == n2:
        return 100.0

    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return 90.0

    # Sequence matcher
    return SequenceMatcher(None, n1, n2).ratio() * 100


def lifespan_match(wd_birth: Optional[int], wd_death: Optional[int],
                   db_birth: Optional[int], db_death: Optional[int]) -> Tuple[float, bool]:
    """
    Calculate lifespan match score.
    Returns (score, is_valid_match)
    """
    score = 0
    checks = 0

    if wd_birth and db_birth:
        checks += 1
        diff = abs(wd_birth - db_birth)
        if diff == 0:
            score += 40
        elif diff <= 2:
            score += 30
        elif diff <= 5:
            score += 20
        elif diff <= 10:
            score += 10
        else:
            # Large discrepancy - likely different person
            return (0, False)

    if wd_death and db_death:
        checks += 1
        diff = abs(wd_death - db_death)
        if diff == 0:
            score += 40
        elif diff <= 2:
            score += 30
        elif diff <= 5:
            score += 20
        elif diff <= 10:
            score += 10
        else:
            return (0, False)

    # If we had checks and they all passed
    is_valid = checks > 0 and score >= 20
    return (score, is_valid)


def build_name_index(db_persons: List[Person]) -> dict:
    """Build an index of normalized names to persons for fast lookup."""
    index = {}
    for person in db_persons:
        # Index by first word of name (usually last name)
        words = person.name.lower().split()
        for word in words:
            if len(word) > 2:
                if word not in index:
                    index[word] = []
                index[word].append(person)
    return index


def find_candidates(name: str, name_index: dict, max_candidates: int = 100) -> List[Person]:
    """Find candidate matches using name index."""
    words = normalize_name(name).split()
    candidates = set()

    for word in words:
        if word in name_index:
            for person in name_index[word][:max_candidates]:
                candidates.add(person)

    return list(candidates)[:max_candidates]


def find_best_match(wikidata_person: dict, db_persons: List[Person], name_index: dict = None) -> MatchResult:
    """Find the best matching person in our DB."""
    wd_name = wikidata_person["name"]
    wd_birth = wikidata_person.get("birth_year")
    wd_death = wikidata_person.get("death_year")
    wd_qid = wikidata_person["qid"]

    best_match = None
    best_score = 0
    best_type = "new"

    # Use index if available
    if name_index:
        candidates = find_candidates(wd_name, name_index)
    else:
        candidates = db_persons

    for person in candidates:
        # Skip if already has different wikidata_id
        if person.wikidata_id and person.wikidata_id != wd_qid:
            continue

        # Calculate name similarity
        name_score = name_similarity(wd_name, person.name)

        # If name score is too low, skip
        if name_score < 50:
            continue

        # Calculate lifespan match
        lifespan_score, is_valid_lifespan = lifespan_match(
            wd_birth, wd_death,
            person.birth_year, person.death_year
        )

        # Total score
        total_score = name_score * 0.6 + lifespan_score

        # Determine match type
        if name_score >= 95 and is_valid_lifespan:
            match_type = "exact"
        elif name_score >= 80 and is_valid_lifespan:
            match_type = "fuzzy"
        elif is_valid_lifespan:
            match_type = "lifespan"
        else:
            match_type = "name_only"

        if total_score > best_score:
            best_score = total_score
            best_match = person
            best_type = match_type

    if best_match and best_score >= 70:
        return MatchResult(
            wikidata_qid=wd_qid,
            wikidata_name=wd_name,
            wikidata_birth=wd_birth,
            wikidata_death=wd_death,
            db_person_id=best_match.id,
            db_person_name=best_match.name,
            match_score=best_score,
            match_type=best_type,
            wikipedia_url=wikidata_person.get("wikipedia_url")
        )
    else:
        return MatchResult(
            wikidata_qid=wd_qid,
            wikidata_name=wd_name,
            wikidata_birth=wd_birth,
            wikidata_death=wd_death,
            db_person_id=None,
            db_person_name=None,
            match_score=best_score if best_match else 0,
            match_type="new",
            wikipedia_url=wikidata_person.get("wikipedia_url")
        )


def main():
    parser = argparse.ArgumentParser(description="Match Wikidata persons to DB")
    parser.add_argument("--input", type=str, required=True, help="Input JSON from fetch script")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--threshold", type=float, default=70, help="Minimum match score")
    parser.add_argument("--dry-run", action="store_true", help="Don't update DB")
    args = parser.parse_args()

    # Load Wikidata persons
    input_path = Path(args.input)
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    wikidata_persons = data["persons"]
    print(f"Loaded {len(wikidata_persons)} Wikidata persons from {input_path}")

    # Load DB persons (only those without wikidata_id or matching category)
    db = SessionLocal()
    try:
        # Get all persons for matching (exclude noise)
        from sqlalchemy import or_, not_
        NOISE_PATTERNS = ["Mrs.%", "Mrs %", "Miss %", "Mr. %", "Mr %"]
        noise_filters = [Person.name.ilike(p) for p in NOISE_PATTERNS]

        db_persons = db.query(Person).filter(
            not_(or_(*noise_filters))
        ).all()
        print(f"Loaded {len(db_persons)} DB persons")

        # Build name index for fast lookup
        print("Building name index...")
        name_index = build_name_index(db_persons)
        print(f"Index built with {len(name_index)} unique words")

        # Match each Wikidata person
        results = []
        matched = 0
        new_persons = 0

        for i, wd_person in enumerate(wikidata_persons):
            if (i + 1) % 100 == 0:
                print(f"  Processing {i+1}/{len(wikidata_persons)}...")

            result = find_best_match(wd_person, db_persons, name_index)
            results.append(result)

            if result.match_type != "new":
                matched += 1
            else:
                new_persons += 1

        # Summary
        print(f"\n=== Results ===")
        print(f"Total Wikidata persons: {len(wikidata_persons)}")
        print(f"Matched to DB: {matched}")
        print(f"New (no match): {new_persons}")

        # Breakdown by match type
        by_type = {}
        for r in results:
            by_type[r.match_type] = by_type.get(r.match_type, 0) + 1
        print(f"\nBy match type:")
        for t, count in sorted(by_type.items()):
            print(f"  {t}: {count}")

        # Show sample matches
        print(f"\nSample matches (score >= {args.threshold}):")
        high_matches = [r for r in results if r.match_score >= args.threshold and r.db_person_id]
        for r in high_matches[:10]:
            print(f"  {r.wikidata_qid}: {r.wikidata_name} ({r.wikidata_birth}-{r.wikidata_death})")
            print(f"    -> DB {r.db_person_id}: {r.db_person_name} (score: {r.match_score:.1f}, type: {r.match_type})")

        # Show sample new persons
        print(f"\nSample new persons (not in DB):")
        new_results = [r for r in results if r.match_type == "new"]
        for r in new_results[:10]:
            print(f"  {r.wikidata_qid}: {r.wikidata_name} ({r.wikidata_birth}-{r.wikidata_death})")

        # Save results
        output_path = args.output or input_path.parent / f"{input_path.stem}_matches.json"
        output_data = {
            "source": str(input_path),
            "total": len(results),
            "matched": matched,
            "new": new_persons,
            "threshold": args.threshold,
            "results": [asdict(r) for r in results]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to {output_path}")

        # Apply matches if not dry-run
        if not args.dry_run:
            print(f"\nApplying {len(high_matches)} matches to DB...")
            updated = 0
            for r in results:
                if r.match_score >= args.threshold and r.db_person_id:
                    person = db.query(Person).filter(Person.id == r.db_person_id).first()
                    if person and not person.wikidata_id:
                        person.wikidata_id = r.wikidata_qid
                        updated += 1

            db.commit()
            print(f"Updated {updated} persons with wikidata_id")

    finally:
        db.close()


if __name__ == "__main__":
    main()
