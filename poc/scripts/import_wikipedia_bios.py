"""
Import Wikipedia biographies from pre-extracted JSONL file.
Uses poc/data/wikipedia_enriched/persons.jsonl

Usage:
    python import_wikipedia_bios.py --limit 1000
    python import_wikipedia_bios.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from app.models.person import Person
from sqlalchemy import or_, func

# Data file
DATA_FILE = Path(__file__).parent.parent / "data" / "wikipedia_enriched" / "persons.jsonl"
CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "wikipedia_bio_import_checkpoint.json"


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"processed_lines": 0, "matched_qid": 0, "matched_name": 0, "updated": 0, "skipped": 0}


def save_checkpoint(cp):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(cp, f, indent=2)


def normalize_name(name: str) -> str:
    """Normalize name for matching."""
    return name.lower().strip().replace("_", " ")


def main():
    parser = argparse.ArgumentParser(description="Import Wikipedia biographies")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to DB")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint")
    parser.add_argument("--batch-size", type=int, default=500, help="Commit batch size")
    args = parser.parse_args()

    if args.reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print("Checkpoint reset.")

    checkpoint = load_checkpoint()
    print(f"Starting from line {checkpoint['processed_lines']}")
    print(f"Previous stats: {checkpoint['matched_qid']} QID, {checkpoint['matched_name']} name, {checkpoint['updated']} updated")

    if not DATA_FILE.exists():
        print(f"Data file not found: {DATA_FILE}")
        return

    db = SessionLocal()

    try:
        # Build lookup of persons needing biography (by QID and name)
        print("Building person lookup...")
        persons_by_qid = {}
        persons_by_name = defaultdict(list)

        query = db.query(Person.id, Person.name, Person.wikidata_id).filter(
            or_(Person.biography.is_(None), Person.biography == '')
        )

        for pid, pname, qid in query.all():
            if qid:
                persons_by_qid[qid] = pid
            persons_by_name[normalize_name(pname)].append(pid)

        print(f"  {len(persons_by_qid)} persons with QID needing bio")
        print(f"  {len(persons_by_name)} unique names needing bio")

        # Process JSONL file
        print(f"\nProcessing {DATA_FILE}...")
        processed = 0
        updated_count = 0
        batch_updates = []

        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                if line_num < checkpoint['processed_lines']:
                    continue

                if args.limit and processed >= args.limit:
                    break

                processed += 1

                try:
                    data = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                summary = data.get('summary', '').strip()
                if not summary or len(summary) < 50:
                    continue

                qid = data.get('qid')
                title = data.get('title', '')

                # Try QID match first
                person_id = None
                match_type = None

                if qid and qid in persons_by_qid:
                    person_id = persons_by_qid[qid]
                    match_type = 'qid'
                    checkpoint['matched_qid'] += 1
                else:
                    # Try name match
                    normalized = normalize_name(title)
                    if normalized in persons_by_name:
                        candidates = persons_by_name[normalized]
                        if len(candidates) == 1:
                            person_id = candidates[0]
                            match_type = 'name'
                            checkpoint['matched_name'] += 1

                if person_id:
                    # Truncate if too long
                    if len(summary) > 2000:
                        summary = summary[:1997] + "..."

                    batch_updates.append((person_id, summary))
                    updated_count += 1

                    # Remove from lookups to avoid duplicate updates
                    if qid and qid in persons_by_qid:
                        del persons_by_qid[qid]
                    normalized = normalize_name(title)
                    if normalized in persons_by_name:
                        persons_by_name[normalized] = [p for p in persons_by_name[normalized] if p != person_id]
                        if not persons_by_name[normalized]:
                            del persons_by_name[normalized]

                # Batch commit
                if len(batch_updates) >= args.batch_size:
                    if not args.dry_run:
                        for pid, bio in batch_updates:
                            db.query(Person).filter(Person.id == pid).update({"biography": bio})
                        db.commit()
                    checkpoint['updated'] += len(batch_updates)
                    checkpoint['processed_lines'] = line_num + 1
                    save_checkpoint(checkpoint)
                    print(f"  Processed {processed}, updated {checkpoint['updated']}")
                    batch_updates = []

        # Final batch
        if batch_updates:
            if not args.dry_run:
                for pid, bio in batch_updates:
                    db.query(Person).filter(Person.id == pid).update({"biography": bio})
                db.commit()
            checkpoint['updated'] += len(batch_updates)
            checkpoint['processed_lines'] += processed
            save_checkpoint(checkpoint)

        print(f"\n=== DONE ===")
        print(f"Processed: {processed}")
        print(f"Matched by QID: {checkpoint['matched_qid']}")
        print(f"Matched by name: {checkpoint['matched_name']}")
        print(f"Total updated: {checkpoint['updated']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
