"""
Import missing servant persons from Wikidata to DB - VERIFIED QIDs
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

# All verified QIDs from Wikidata searches
VERIFIED_QIDS = {
    # Irish/Celtic
    "Q1209163": "Diarmuid Ua Duibhne",
    "Q387800": "Fergus mac Róich",
    "Q382610": "Fionn mac Cumhaill",
    "Q1141828": "Medb",
    "Q1888724": "Manannán mac Lir",
    "Q930509": "Scáthach",

    # Norse
    "Q131087": "Valkyrie",
    "Q827758": "Þrúðr",
    "Q244032": "Skaði",

    # Japanese
    "Q267549": "Okita Sōji",
    "Q701182": "Hijikata Toshizō",
    "Q138256": "Saitō Hajime",
    "Q590523": "Minamoto no Yorimitsu",
    "Q316898": "Musashibō Benkei",
    "Q1368291": "Fūma Kotarō",
    "Q986527": "Shuten-dōji",
    "Q5983716": "Ibaraki-dōji",
    "Q1207544": "Kiyohime",
    "Q231603": "Sei Shōnagon",
    "Q7676361": "Taira no Kagekiyo",
    "Q1047529": "Kintarō",
    "Q6582069": "Watanabe no Tsuna",
    "Q1136623": "Fujiwara no Hidesato",
    "Q1085443": "Mochizuki Chiyome",
    "Q6378605": "Katō Danzō",
    "Q10490430": "Hōzōin Inshun",
    "Q631099": "Yagyū Munenori",
    "Q3044815": "Oda Nobukatsu",
    "Q1339356": "Minamoto no Tametomo",
    "Q463142": "Kyokutei Bakin",
    "Q3058220": "Okada Izō",
    "Q305477": "Sen no Rikyū",
    "Q1334304": "Izumo no Okuni",
    "Q17209288": "Osakabehime",
    "Q1071391": "Mori Nagayoshi",
    "Q276404": "Takeda Shingen",

    # Chinese
    "Q3275211": "Consort Yu",
    "Q532410": "Jing Ke",
    "Q697515": "Li Shuwen",
    "Q836134": "Yan Qing",
    "Q1321898": "Red Hare",
    "Q317846": "Lü Bu",
    "Q701488": "Jiang Ziya",
    "Q710336": "Gao Changgong",
    "Q2994191": "Tai Sui",
    "Q1759916": "Daikokuten",

    # Greek/Mesopotamian
    "Q129866": "Minotaur",
    "Q1132772": "Caeneus",
    "Q463220": "Enkidu",
    "Q654458": "Ereshkigal",
    "Q202387": "Astraea",  # Greek goddess

    # Indian
    "Q170485": "Parvati",
    "Q181878": "Rani Lakshmibai",
    "Q2044550": "Ashwatthama",
    "Q797498": "Vritra",
    "Q113155": "Kamadeva",

    # European
    "Q715027": "Chevalier d'Éon",
    "Q213518": "Blackbeard",
    "Q231549": "Anne Bonny",
    "Q1163427": "Bradamante",
    "Q53997876": "Mandricardo",
    "Q283111": "Professor Moriarty",
    "Q37142": "Constantine XI Palaiologos",
    "Q168261": "Ptolemy I Soter",
    "Q310739": "Hephaestion",
    "Q239355": "Solomon ibn Gabirol",
    "Q543379": "Kriemhild",  # Nibelungenlied

    # Vietnamese
    "Q1207428": "Trưng Sisters",

    # American
    "Q118352128": "Abigail Williams",
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
    log_lines = []

    for qid, expected_name in VERIFIED_QIDS.items():
        # Check if already exists
        cur.execute("SELECT id, name FROM persons WHERE wikidata_id = %s", (qid,))
        existing = cur.fetchone()

        if existing:
            already_exists += 1
            log_lines.append(f"EXISTS: {expected_name} ({qid}) -> id={existing[0]}")
            continue

        # Get details from Wikidata
        details = get_wikidata_details(qid)
        if not details or not details["name"]:
            failed.append((qid, expected_name))
            log_lines.append(f"FAILED: {expected_name} ({qid}) - no data from Wikidata")
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
            log_lines.append(f"ADDED: {details['name']} ({qid}) -> id={new_id}")
            added += 1
        except Exception as e:
            conn.rollback()
            failed.append((qid, expected_name))
            log_lines.append(f"ERROR: {expected_name} ({qid}) - {str(e)[:50]}")

        time.sleep(0.3)

    conn.close()

    # Save log
    log_path = PROJECT_ROOT / "poc/data/import_persons_log.txt"
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
        f.write(f"\n\n=== Summary ===\n")
        f.write(f"Already in DB: {already_exists}\n")
        f.write(f"Added: {added}\n")
        f.write(f"Failed: {len(failed)}\n")
        if failed:
            f.write(f"Failed list:\n")
            for qid, name in failed:
                f.write(f"  {name} ({qid})\n")

    print(f"=== Summary ===")
    print(f"Already in DB: {already_exists}")
    print(f"Added: {added}")
    print(f"Failed: {len(failed)}")
    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    import_missing()
