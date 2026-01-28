"""
Fetch Wikipedia biographies for persons with Wikidata IDs.
Uses Wikipedia REST API - no LLM needed.

Usage:
    python fetch_wikipedia_bios.py --limit 1000 --batch-size 50
"""

import argparse
import json
import time
import sys
from pathlib import Path
from datetime import datetime

import httpx
from sqlalchemy import or_

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from app.models.person import Person

# Wikipedia API
WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Checkpoint file
CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "wikipedia_bio_checkpoint.json"


def load_checkpoint():
    """Load checkpoint to resume from last position."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"processed_ids": [], "last_id": 0, "success": 0, "failed": 0}


def save_checkpoint(checkpoint):
    """Save checkpoint."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f)


def get_wikipedia_title_from_qid(qid: str, client: httpx.Client) -> str | None:
    """Get Wikipedia article title from Wikidata QID."""
    try:
        resp = client.get(WIKIDATA_API, params={
            "action": "wbgetentities",
            "ids": qid,
            "props": "sitelinks",
            "sitefilter": "enwiki",
            "format": "json"
        })
        if resp.status_code == 200:
            data = resp.json()
            entities = data.get("entities", {})
            if qid in entities:
                sitelinks = entities[qid].get("sitelinks", {})
                if "enwiki" in sitelinks:
                    return sitelinks["enwiki"]["title"]
    except Exception as e:
        print(f"  Error getting wiki title for {qid}: {e}")
    return None


def get_wikipedia_summary(title: str, client: httpx.Client) -> str | None:
    """Get Wikipedia summary for article title."""
    try:
        # URL encode the title
        encoded_title = title.replace(" ", "_")
        resp = client.get(f"{WIKIPEDIA_API}/{encoded_title}")
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract")
            if extract and len(extract) > 50:  # Minimum length
                return extract
    except Exception as e:
        print(f"  Error getting summary for {title}: {e}")
    return None


def process_batch(persons: list, client: httpx.Client, db, checkpoint: dict, dry_run: bool = False):
    """Process a batch of persons."""
    for person in persons:
        if person.id in checkpoint["processed_ids"]:
            continue

        print(f"Processing: {person.name} (ID: {person.id}, QID: {person.wikidata_id})")

        # Get Wikipedia title from Wikidata
        title = get_wikipedia_title_from_qid(person.wikidata_id, client)
        if not title:
            print(f"  No Wikipedia article found")
            checkpoint["processed_ids"].append(person.id)
            checkpoint["failed"] += 1
            continue

        print(f"  Wikipedia: {title}")

        # Get summary
        summary = get_wikipedia_summary(title, client)
        if not summary:
            print(f"  No summary available")
            checkpoint["processed_ids"].append(person.id)
            checkpoint["failed"] += 1
            continue

        # Truncate if too long (keep first 2000 chars)
        if len(summary) > 2000:
            summary = summary[:1997] + "..."

        print(f"  Got biography ({len(summary)} chars)")

        if not dry_run:
            person.biography = summary
            db.commit()

        checkpoint["processed_ids"].append(person.id)
        checkpoint["last_id"] = person.id
        checkpoint["success"] += 1

        # Rate limiting - be nice to Wikipedia
        time.sleep(0.5)

    return checkpoint


def main():
    parser = argparse.ArgumentParser(description="Fetch Wikipedia biographies")
    parser.add_argument("--limit", type=int, default=100, help="Max persons to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for commits")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to DB")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint")
    args = parser.parse_args()

    if args.reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print("Checkpoint reset.")

    checkpoint = load_checkpoint()
    print(f"Starting from checkpoint: {checkpoint['success']} success, {checkpoint['failed']} failed")

    db = SessionLocal()

    try:
        # Get persons with Wikidata ID but no biography
        query = db.query(Person).filter(
            Person.wikidata_id.isnot(None),
            Person.wikidata_id != '',
            or_(Person.biography.is_(None), Person.biography == '')
        )

        # Skip already processed
        if checkpoint["processed_ids"]:
            query = query.filter(~Person.id.in_(checkpoint["processed_ids"]))

        persons = query.order_by(Person.id).limit(args.limit).all()

        print(f"Found {len(persons)} persons to process")

        if not persons:
            print("No more persons to process!")
            return

        with httpx.Client(timeout=30.0) as client:
            for i in range(0, len(persons), args.batch_size):
                batch = persons[i:i + args.batch_size]
                print(f"\n--- Batch {i // args.batch_size + 1} ({len(batch)} persons) ---")
                checkpoint = process_batch(batch, client, db, checkpoint, args.dry_run)
                save_checkpoint(checkpoint)
                print(f"Progress: {checkpoint['success']} success, {checkpoint['failed']} failed")

        print(f"\n=== DONE ===")
        print(f"Total success: {checkpoint['success']}")
        print(f"Total failed: {checkpoint['failed']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
