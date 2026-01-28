"""
Import missing servant persons from Wikidata to DB
"""
import json
import time
import re
import requests
import psycopg2
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "ChaldeasBot/1.0 (https://chaldeas.site)"}

# QIDs that need to be imported (from map_all_servants.py MANUAL_QIDS)
MISSING_QIDS = {
    # Irish/Celtic
    "Q1207617": "Diarmuid Ua Duibhne",
    "Q1167219": "Fergus mac Róich",
    "Q316752": "Fionn mac Cumhaill",
    "Q1569540": "Medb",
    "Q744934": "Manannán mac Lir",
    "Q2265531": "Scáthach",

    # Norse
    "Q127918": "Valkyrie",
    "Q2408920": "Thrúd",
    "Q25280": "Skaði",

    # Japanese
    "Q1204104": "Okita Sōji",
    "Q708972": "Hijikata Toshizō",
    "Q1196854": "Saitō Hajime",
    "Q1392067": "Minamoto no Yorimitsu",
    "Q856221": "Benkei",
    "Q1149547": "Fūma Kotarō",
    "Q2386749": "Shuten-dōji",
    "Q1654143": "Ibaraki-dōji",
    "Q193145": "Yamata no Orochi",
    "Q1094633": "Kiyohime",
    "Q193538": "Sei Shōnagon",
    "Q1335839": "Taira no Kagekiyo",
    "Q633626": "Kintarō",
    "Q1195100": "Watanabe no Tsuna",
    "Q1361459": "Fujiwara no Hidesato",
    "Q3319090": "Mochizuki Chiyome",
    "Q3194518": "Katō Danzō",
    "Q3140897": "Hōzōin In'ei",
    "Q1245418": "Yagyū Munenori",
    "Q3349931": "Oda Nobukatsu",
    "Q1277366": "Minamoto no Tametomo",
    "Q11475893": "Kiichi Hōgen",
    "Q315768": "Kyokutei Bakin",
    "Q1079155": "Okada Izō",
    "Q319493": "Sen no Rikyū",
    "Q467508": "Izumo no Okuni",
    "Q7104907": "Osakabe",
    "Q11354915": "Beni-Enma",
    "Q1231376": "Mori Nagayoshi",
    "Q187800": "Takeda Shingen",

    # Chinese
    "Q262608": "Lady Yu",
    "Q714867": "Jing Ke",
    "Q6542666": "Li Shuwen",
    "Q8048329": "Yan Qing",
    "Q1073099": "Red Hare",
    "Q249040": "Lü Bu",
    "Q712851": "Jiang Ziya",
    "Q712639": "Gao Changgong",
    "Q10916867": "Taisui Xingjun",
    "Q854697": "Daikokuten",

    # Greek
    "Q130106": "Minotaur",
    "Q148919": "Astraea",
    "Q1025254": "Caeneus",
    "Q208170": "Enkidu",
    "Q212913": "Ereshkigal",

    # Indian
    "Q191255": "Parvati",
    "Q232538": "Rani of Jhansi",
    "Q758371": "Ashwatthama",
    "Q1195882": "Vritra",
    "Q628269": "Kama",

    # European
    "Q378929": "Chevalier d'Éon",
    "Q188434": "Blackbeard",
    "Q273615": "Anne Bonny",
    "Q934561": "Bradamante",
    "Q3844605": "Mandricardo",
    "Q1346515": "Phantom of the Opera",
    "Q1376407": "Professor Moriarty",
    "Q180377": "Dr Jekyll and Mr Hyde",
    "Q81474": "Constantine XI Palaiologos",
    "Q192410": "Ptolemy I Soter",
    "Q133798": "Hephaestion",
    "Q179461": "Solomon ibn Gabirol",
    "Q543379": "Kriemhild",

    # Vietnamese
    "Q1152634": "Trưng Sisters",

    # American
    "Q2560763": "Abigail Williams",
}


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


def import_missing():
    """Import missing persons to DB"""
    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor()

    added = 0
    already_exists = 0
    failed = []

    for qid, expected_name in MISSING_QIDS.items():
        # Check if already exists
        cur.execute("SELECT id, name FROM persons WHERE wikidata_id = %s", (qid,))
        existing = cur.fetchone()

        if existing:
            already_exists += 1
            print(f"  EXISTS: {expected_name} ({qid}) -> id={existing[0]}")
            continue

        # Get details from Wikidata
        details = get_wikidata_details(qid)
        if not details or not details["name"]:
            failed.append((qid, expected_name))
            print(f"  FAILED: {expected_name} ({qid})")
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
            print(f"  ADDED: {details['name']} ({qid}) -> id={new_id}")
            added += 1
        except Exception as e:
            conn.rollback()
            failed.append((qid, expected_name))
            print(f"  ERROR: {expected_name} ({qid}) - {str(e)[:50]}")

        time.sleep(0.3)

    conn.close()

    print(f"\n=== Summary ===")
    print(f"Already in DB: {already_exists}")
    print(f"Added: {added}")
    print(f"Failed: {len(failed)}")
    if failed:
        print(f"Failed list:")
        for qid, name in failed:
            print(f"  {name} ({qid})")


if __name__ == "__main__":
    import_missing()
