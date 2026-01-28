"""
Fetch Wikidata source data for matched persons

For persons who already have wikidata_id, fetch additional data:
- Wikipedia URLs (en, ko, etc.)
- Image URLs
- Full descriptions
- External IDs (VIAF, GND, etc.)

Usage:
    python poc/scripts/fetch_wikidata_sources.py --limit 1000
    python poc/scripts/fetch_wikidata_sources.py --limit 5000 --batch-size 50
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import time
import argparse
import threading
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import requests

# Thread-safe print
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()


@dataclass
class WikidataSourceData:
    """Source data fetched from Wikidata"""
    qid: str
    person_id: int
    wikipedia_en: Optional[str] = None
    wikipedia_ko: Optional[str] = None
    image_url: Optional[str] = None
    description_en: Optional[str] = None
    description_ko: Optional[str] = None
    viaf_id: Optional[str] = None
    gnd_id: Optional[str] = None


class WikidataSourceFetcher:
    """Fetches full entity data from Wikidata API"""

    API_URL = "https://www.wikidata.org/w/api.php"
    COMMONS_URL = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self.last_call = 0
        self._lock = threading.Lock()

    def _rate_limit(self):
        with self._lock:
            now = time.time()
            wait = self.delay - (now - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.time()

    def fetch_entity(self, qid: str, person_id: int) -> Optional[WikidataSourceData]:
        """Fetch full entity data for a QID"""
        self._rate_limit()

        try:
            resp = requests.get(
                self.API_URL,
                params={
                    "action": "wbgetentities",
                    "ids": qid,
                    "props": "labels|descriptions|sitelinks|claims",
                    "languages": "en|ko",
                    "sitefilter": "enwiki|kowiki",
                    "format": "json"
                },
                headers={"User-Agent": "CHALDEAS/1.0 (historical data project)"},
                timeout=30
            )

            if resp.status_code == 429:
                safe_print(f"  [RATE LIMIT] Waiting 60s...")
                time.sleep(60)
                return self.fetch_entity(qid, person_id)  # Retry

            if resp.status_code != 200:
                return None

            data = resp.json()
            entity = data.get("entities", {}).get(qid, {})

            if "missing" in entity:
                return None

            # Extract sitelinks (Wikipedia URLs)
            sitelinks = entity.get("sitelinks", {})
            wikipedia_en = None
            wikipedia_ko = None

            if "enwiki" in sitelinks:
                title = sitelinks["enwiki"].get("title", "")
                wikipedia_en = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

            if "kowiki" in sitelinks:
                title = sitelinks["kowiki"].get("title", "")
                wikipedia_ko = f"https://ko.wikipedia.org/wiki/{title.replace(' ', '_')}"

            # Extract descriptions
            descriptions = entity.get("descriptions", {})
            description_en = descriptions.get("en", {}).get("value")
            description_ko = descriptions.get("ko", {}).get("value")

            # Extract image (P18)
            claims = entity.get("claims", {})
            image_url = None
            if "P18" in claims:
                image_claims = claims["P18"]
                if image_claims:
                    image_name = image_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                    if image_name:
                        image_url = self._get_commons_url(image_name)

            # Extract external IDs
            viaf_id = None
            gnd_id = None

            if "P214" in claims:  # VIAF
                viaf_claims = claims["P214"]
                if viaf_claims:
                    viaf_id = viaf_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")

            if "P227" in claims:  # GND
                gnd_claims = claims["P227"]
                if gnd_claims:
                    gnd_id = gnd_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")

            return WikidataSourceData(
                qid=qid,
                person_id=person_id,
                wikipedia_en=wikipedia_en,
                wikipedia_ko=wikipedia_ko,
                image_url=image_url,
                description_en=description_en,
                description_ko=description_ko,
                viaf_id=viaf_id,
                gnd_id=gnd_id
            )

        except Exception as e:
            safe_print(f"  [ERROR] {qid}: {e}")
            return None

    def _get_commons_url(self, filename: str) -> str:
        """Convert Commons filename to URL"""
        import hashlib
        filename = filename.replace(" ", "_")
        md5 = hashlib.md5(filename.encode()).hexdigest()
        return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[:2]}/{filename}"


def load_persons_with_wikidata(limit: int = 1000, offset: int = 0):
    """Load persons who have wikidata_id but need source data"""
    from app.db.session import SessionLocal
    from app.models.person import Person

    db = SessionLocal()
    try:
        # Get persons with wikidata_id but without wikipedia_url
        query = db.query(Person).filter(
            Person.wikidata_id.isnot(None),
            Person.wikipedia_url.is_(None)
        ).order_by(Person.id).offset(offset).limit(limit)

        persons = []
        for p in query:
            persons.append({
                "id": p.id,
                "name": p.name,
                "wikidata_id": p.wikidata_id
            })

        return persons
    finally:
        db.close()


def apply_source_data(results: List[WikidataSourceData]):
    """Apply fetched source data to persons"""
    from app.db.session import SessionLocal
    from app.models.person import Person

    db = SessionLocal()
    try:
        updated = 0
        for result in results:
            if not result:
                continue

            person = db.query(Person).filter(Person.id == result.person_id).first()
            if person:
                # Update person with fetched data
                if result.wikipedia_en and not person.wikipedia_url:
                    person.wikipedia_url = result.wikipedia_en
                if result.image_url and not person.image_url:
                    person.image_url = result.image_url
                if result.description_en and not person.biography:
                    person.biography = result.description_en
                if result.description_ko and not person.biography_ko:
                    person.biography_ko = result.description_ko
                updated += 1

        db.commit()
        return updated
    finally:
        db.close()


def save_checkpoint(results: List[WikidataSourceData], offset: int):
    """Save checkpoint for resumability"""
    checkpoint_path = Path(__file__).parent.parent / "data" / "wikidata_sources_checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "last_offset": offset,
        "count": len([r for r in results if r]),
        "results": [asdict(r) for r in results if r]
    }

    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Fetch Wikidata source data")
    parser.add_argument("--limit", type=int, default=1000, help="Number of persons to process")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination")
    parser.add_argument("--batch-size", type=int, default=100, help="Apply to DB every N records")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between API calls")
    args = parser.parse_args()

    safe_print("=== Wikidata Source Fetcher ===")
    safe_print(f"Limit: {args.limit}, Offset: {args.offset}, Delay: {args.delay}s")

    # Load persons
    safe_print("Loading persons with wikidata_id...")
    persons = load_persons_with_wikidata(args.limit, args.offset)
    safe_print(f"Loaded {len(persons)} persons")

    if not persons:
        safe_print("No persons to process")
        return

    # Initialize fetcher
    fetcher = WikidataSourceFetcher(delay=args.delay)

    # Process
    results = []
    stats = {"success": 0, "no_data": 0, "errors": 0}

    for i, person in enumerate(persons, 1):
        result = fetcher.fetch_entity(person["wikidata_id"], person["id"])

        if result:
            results.append(result)
            has_wiki = "✓" if result.wikipedia_en else "✗"
            has_img = "✓" if result.image_url else "✗"
            safe_print(f"[{i}/{len(persons)}] {person['name']} -> wiki:{has_wiki} img:{has_img}")
            stats["success"] += 1
        else:
            results.append(None)
            safe_print(f"[{i}/{len(persons)}] {person['name']} -> no data")
            stats["no_data"] += 1

        # Batch apply
        if i % args.batch_size == 0:
            batch_results = [r for r in results[-args.batch_size:] if r]
            if batch_results:
                updated = apply_source_data(batch_results)
                safe_print(f"  [Applied {updated} to DB]")
            save_checkpoint(results, args.offset + i)

    # Final apply
    remaining = [r for r in results[-(len(results) % args.batch_size):] if r]
    if remaining:
        updated = apply_source_data(remaining)
        safe_print(f"  [Applied {updated} to DB]")

    save_checkpoint(results, args.offset + len(persons))

    # Summary
    safe_print()
    safe_print("=== Summary ===")
    safe_print(f"Processed: {len(persons)}")
    safe_print(f"Success: {stats['success']}")
    safe_print(f"No data: {stats['no_data']}")

    with_wiki = sum(1 for r in results if r and r.wikipedia_en)
    with_img = sum(1 for r in results if r and r.image_url)
    safe_print(f"With Wikipedia URL: {with_wiki}")
    safe_print(f"With Image: {with_img}")


if __name__ == "__main__":
    main()
