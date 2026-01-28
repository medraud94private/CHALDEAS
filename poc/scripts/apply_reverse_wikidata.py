"""
Apply Reverse Wikidata Collection Results to DB

Reads wikidata_*_matches.json files and:
1. Updates existing persons with wikidata_id (matched)
2. Inserts new persons from Wikidata (new)

Usage:
    python poc/scripts/apply_reverse_wikidata.py [--dry-run]
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from app.models.person import Person


def load_match_files():
    """Load all reverse match files"""
    data_dir = Path(__file__).parent.parent / "data"

    files = [
        "wikidata_philosophers_matches.json",
        "wikidata_rulers_matches.json",
        "wikidata_military_matches.json",
        "wikidata_scientists_matches.json",
        "wikidata_religious_matches.json",
        "wikidata_philosophers_ext_matches.json",
        "wikidata_rulers_ext_matches.json",
    ]

    all_results = []
    for fname in files:
        fpath = data_dir / fname
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                category = fname.replace("wikidata_", "").replace("_matches.json", "")
                for r in data.get("results", []):
                    r["category"] = category
                all_results.extend(data.get("results", []))
                print(f"Loaded {len(data.get('results', []))} from {fname}")

    return all_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update DB")
    parser.add_argument("--skip-new", action="store_true", help="Skip inserting new persons")
    parser.add_argument("--min-score", type=float, default=70.0, help="Minimum match score for updates")
    args = parser.parse_args()

    results = load_match_files()
    print(f"\nTotal results: {len(results)}")

    # Separate matched vs new
    matched = [r for r in results if r.get("db_person_id") and r.get("match_score", 0) >= args.min_score]
    new_persons = [r for r in results if r.get("match_type") == "new"]

    print(f"Matched (score >= {args.min_score}): {len(matched)}")
    print(f"New persons: {len(new_persons)}")

    if args.dry_run:
        print("\n[DRY RUN] Would update:")
        for r in matched[:5]:
            print(f"  {r['db_person_id']}: {r['db_person_name']} -> {r['wikidata_qid']} (score: {r['match_score']:.1f})")
        if len(matched) > 5:
            print(f"  ... and {len(matched) - 5} more")

        if not args.skip_new:
            print("\n[DRY RUN] Would insert:")
            for r in new_persons[:5]:
                print(f"  {r['wikidata_qid']}: {r['wikidata_name']} ({r.get('wikidata_birth', '?')}-{r.get('wikidata_death', '?')})")
            if len(new_persons) > 5:
                print(f"  ... and {len(new_persons) - 5} more")
        return

    db = SessionLocal()
    try:
        # 1. Update matched persons
        updated = 0
        for r in matched:
            person = db.query(Person).filter(Person.id == r["db_person_id"]).first()
            if person and not person.wikidata_id:  # Don't overwrite existing
                person.wikidata_id = r["wikidata_qid"]
                updated += 1

        print(f"\nUpdated {updated} persons with wikidata_id")

        # 2. Insert new persons
        inserted = 0
        skipped_dupes = 0
        if not args.skip_new:
            import re
            # Dedupe new_persons by wikidata_qid (same person may appear in multiple categories)
            seen_qids = set()
            unique_new = []
            for r in new_persons:
                qid = r["wikidata_qid"]
                if qid not in seen_qids:
                    seen_qids.add(qid)
                    unique_new.append(r)
                else:
                    skipped_dupes += 1

            if skipped_dupes:
                print(f"Skipped {skipped_dupes} duplicate entries")

            for r in unique_new:
                # Check if already exists by wikidata_id
                existing = db.query(Person).filter(Person.wikidata_id == r["wikidata_qid"]).first()
                if existing:
                    continue

                # Create new person with unique slug
                name = r["wikidata_name"]
                qid = r["wikidata_qid"].lower()  # e.g., q63500
                base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                slug = f"{base_slug}-{qid}"  # Make unique with QID

                # Double-check slug doesn't exist
                existing_slug = db.query(Person).filter(Person.slug == slug).first()
                if existing_slug:
                    print(f"  WARN: slug {slug} already exists, skipping")
                    continue

                new_person = Person(
                    name=name,
                    slug=slug,
                    wikidata_id=r["wikidata_qid"],
                    birth_year=r.get("wikidata_birth"),
                    death_year=r.get("wikidata_death"),
                    wikipedia_url=r.get("wikipedia_url"),
                    role=r.get("category"),  # philosopher, ruler, military
                )
                db.add(new_person)
                inserted += 1

            print(f"Inserted {inserted} new persons")

        # Flush before commit to catch any DB errors
        print("\nFlushing changes...")
        try:
            db.flush()
            print("Flush successful, committing...")
            db.commit()
            print(f"\nDone! Updated: {updated}, Inserted: {inserted}")
        except Exception as e:
            print(f"ERROR during commit: {e}")
            db.rollback()
            raise

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
