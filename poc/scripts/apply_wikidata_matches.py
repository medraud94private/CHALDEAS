"""
Apply Wikidata Match Results to DB

Reads the match results JSON and updates persons table with wikidata_id.

Usage:
    python poc/scripts/apply_wikidata_matches.py [--dry-run]
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from app.models.person import Person


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update DB")
    parser.add_argument("--input", type=str, default=None, help="Input JSON file (default: auto-detect)")
    parser.add_argument("--min-confidence", type=float, default=0.95, help="Minimum confidence to apply")
    args = parser.parse_args()

    # Load results - auto-detect or use specified file
    data_dir = Path(__file__).parent.parent / "data"

    if args.input:
        results_path = Path(args.input)
    else:
        # Prefer parallel results if exists, fall back to single-thread results
        parallel_path = data_dir / "wikidata_parallel_results.json"
        single_path = data_dir / "wikidata_match_results.json"

        if parallel_path.exists():
            results_path = parallel_path
        elif single_path.exists():
            results_path = single_path
        else:
            print(f"ERROR: No results file found in {data_dir}")
            return

    if not results_path.exists():
        print(f"ERROR: Results file not found: {results_path}")
        return

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data["results"]
    print(f"Loaded {len(results)} results from {results_path}")

    # Filter matched only (handle both qid key names from different scripts)
    def get_qid(r):
        return r.get("wikidata_qid") or r.get("wikidata_id")

    def get_confidence(r):
        return r.get("confidence") or r.get("match_confidence") or 0

    matched = [r for r in results if get_qid(r) and get_confidence(r) >= args.min_confidence]
    total_with_qid = len([r for r in results if get_qid(r)])
    print(f"With QID: {total_with_qid}")
    print(f"Matched (confidence >= {args.min_confidence}): {len(matched)}")

    if args.dry_run:
        print("\n[DRY RUN] Would update:")
        for r in matched[:10]:
            qid = get_qid(r)
            conf = get_confidence(r)
            print(f"  {r['person_id']}: {r['person_name']} -> {qid} (conf: {conf:.2f})")
        if len(matched) > 10:
            print(f"  ... and {len(matched) - 10} more")
        return

    # Update DB
    db = SessionLocal()
    try:
        updated = 0
        for r in matched:
            person = db.query(Person).filter(Person.id == r["person_id"]).first()
            if person:
                person.wikidata_id = get_qid(r)
                updated += 1

        db.commit()
        print(f"\nUpdated {updated} persons with wikidata_id")

    finally:
        db.close()


if __name__ == "__main__":
    main()
