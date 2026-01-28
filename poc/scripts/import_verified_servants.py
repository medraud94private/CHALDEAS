"""
확인된 FGO 서번트 QID를 DB에 임포트
"""
import json
import time
import re
import requests
import psycopg2
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
VERIFIED_PATH = PROJECT_ROOT / "data/raw/atlas_academy/verified_servant_qids.json"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "ChaldeasBot/1.0 (https://chaldeas.site)"}


def get_wikidata_details(qid: str) -> dict:
    """Get detailed info from Wikidata"""
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "format": "json",
        "languages": "en|ko|ja",
        "props": "labels|descriptions|claims"
    }

    try:
        resp = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=30)
        data = resp.json()

        if "entities" not in data or qid not in data["entities"]:
            return None

        entity = data["entities"][qid]

        name_en = entity.get("labels", {}).get("en", {}).get("value")
        name_ko = entity.get("labels", {}).get("ko", {}).get("value")
        desc_en = entity.get("descriptions", {}).get("en", {}).get("value")

        claims = entity.get("claims", {})
        birth_year = None
        death_year = None

        if "P569" in claims:
            try:
                time_val = claims["P569"][0]["mainsnak"]["datavalue"]["value"]["time"]
                if time_val.startswith("+"):
                    birth_year = int(time_val[1:5])
                elif time_val.startswith("-"):
                    birth_year = -int(time_val[1:5])
            except:
                pass

        if "P570" in claims:
            try:
                time_val = claims["P570"][0]["mainsnak"]["datavalue"]["value"]["time"]
                if time_val.startswith("+"):
                    death_year = int(time_val[1:5])
                elif time_val.startswith("-"):
                    death_year = -int(time_val[1:5])
            except:
                pass

        return {
            "wikidata_id": qid,
            "name": name_en,
            "name_ko": name_ko,
            "description": desc_en,
            "birth_year": birth_year,
            "death_year": death_year,
        }

    except Exception as e:
        print(f"Error fetching {qid}: {e}")
        return None


def import_verified():
    """Import verified servants to DB"""
    # Load verified QIDs
    with open(VERIFIED_PATH, encoding='utf-8') as f:
        data = json.load(f)

    verified = data["verified"]
    print(f"Verified servants: {len(verified)}")

    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor()

    added = 0
    already_exists = 0
    failed = []

    for name, info in verified.items():
        qid = info["qid"]

        # Check if already exists
        cur.execute("SELECT id, name FROM persons WHERE wikidata_id = %s", (qid,))
        existing = cur.fetchone()

        if existing:
            already_exists += 1
            print(f"  EXISTS: {name} ({qid}) -> id={existing[0]}")
            continue

        # Get details from Wikidata
        details = get_wikidata_details(qid)
        if not details or not details["name"]:
            failed.append(name)
            print(f"  FAILED: {name} ({qid})")
            continue

        # Generate slug
        slug = re.sub(r'[^a-z0-9]+', '-', details["name"].lower()).strip('-')
        slug = f"{slug}-{qid.lower()}"

        try:
            cur.execute("""
                INSERT INTO persons (wikidata_id, name, name_ko, slug, biography, birth_year, death_year, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (
                details["wikidata_id"],
                details["name"],
                details["name_ko"],
                slug,
                details["description"],
                details["birth_year"],
                details["death_year"]
            ))
            new_id = cur.fetchone()[0]
            conn.commit()
            print(f"  ADDED: {name} ({qid}) -> id={new_id}")
            added += 1
        except Exception as e:
            conn.rollback()
            failed.append(name)
            print(f"  ERROR: {name} ({qid}) - {str(e)[:50]}")

        time.sleep(0.3)

    conn.close()

    print(f"\n=== Summary ===")
    print(f"Already in DB: {already_exists}")
    print(f"Added: {added}")
    print(f"Failed: {len(failed)}")
    if failed:
        print(f"Failed list: {failed}")


if __name__ == "__main__":
    import_verified()
