"""
누락된 FGO 서번트를 Wikidata에서 가져와서 DB에 추가
"""
import json
import time
import requests
import psycopg2
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# 수정된 FGO 서번트 → Wikidata QID 매핑
SERVANT_QIDS = {
    # Saber
    "Altria Pendragon": "Q45792",  # King Arthur (legendary figure)
    "Nero Claudius": "Q1413",
    "Gaius Julius Caesar": "Q1048",
    "Siegfried": "Q152952",
    "Gawain": "Q193969",
    "Lancelot": "Q214963",
    "Mordred": "Q1087720",
    "Bedivere": "Q815472",
    "Fergus mac Roich": "Q1307208",
    "Musashi Miyamoto": "Q319824",
    "Okita Souji": "Q1045108",
    "Diarmuid Ua Duibhne": "Q1129108",

    # Archer
    "Gilgamesh": "Q159709",  # Sumerian ruler (FIXED!)
    "Robin Hood": "Q122756",
    "Atalante": "Q171167",
    "Arjuna": "Q623218",
    "Nikola Tesla": "Q9036",
    "Napoleon": "Q517",
    "Paris": "Q167406",
    "Chiron": "Q41602",

    # Lancer
    "Cu Chulainn": "Q212903",
    "Leonidas I": "Q152619",
    "Romulus": "Q6116",
    "Hektor": "Q168395",
    "Scathach": "Q1062699",
    "Karna": "Q732622",
    "Brynhildr": "Q152983",
    "Vlad III": "Q43718",
    "Enkidu": "Q155826",

    # Rider
    "Alexander": "Q8409",
    "Medusa": "Q38143",
    "Boudica": "Q130746",
    "Francis Drake": "Q36517",
    "Achilles": "Q41746",
    "Ushiwakamaru": "Q189346",
    "Ivan the Terrible": "Q7994",
    "Christopher Columbus": "Q7322",
    "Marie Antoinette": "Q47365",
    "Ozymandias": "Q1279",
    "Quetzalcoatl": "Q177903",

    # Caster
    "Medea": "Q188836",
    "Hans Christian Andersen": "Q5673",
    "William Shakespeare": "Q692",
    "Tamamo-no-Mae": "Q1264785",
    "Solomon": "Q36195",
    "Merlin": "Q188958",
    "Leonardo da Vinci": "Q762",
    "Xuanzang Sanzang": "Q628641",
    "Gilgamesh (Caster)": "Q159709",
    "Paracelsus": "Q83428",
    "Thomas Edison": "Q8743",
    "Helena Blavatsky": "Q179991",
    "Circe": "Q134762",
    "Scheherazade": "Q1186638",
    "Anastasia Nikolaevna": "Q159544",
    "Avicebron": "Q148629",

    # Assassin
    "Sasaki Kojiro": "Q1261989",
    "Stheno": "Q1265131",
    "Mata Hari": "Q36108",
    "Jack the Ripper": "Q46700",
    "Carmilla": "Q432294",
    "Shuten-douji": "Q2370889",
    "Cleopatra": "Q635",
    "Semiramis": "Q172847",
    "First Hassan": None,
    "Wu Zetian": "Q48993",
    "Charlotte Corday": "Q273022",
    "Okada Izo": "Q6149652",

    # Berserker
    "Heracles": "Q122248",
    "Lancelot (Berserker)": "Q214963",
    "Spartacus": "Q46405",
    "Caligula": "Q1409",
    "Darius III": "Q130368",
    "Kiyohime": "Q3254291",
    "Eric Bloodaxe": "Q314772",
    "Tamamo Cat": None,
    "Frankenstein": "Q150827",
    "Beowulf": "Q180061",
    "Nightingale": "Q37103",
    "Cu Chulainn (Alter)": "Q212903",
    "Penthesilea": "Q267006",
    "Paul Bunyan": "Q378792",
    "Atalante (Alter)": "Q171167",

    # Ruler
    "Jeanne d'Arc": "Q7226",
    "Amakusa Shirou": "Q1137917",
    "Sherlock Holmes": "Q3295578",
    "Qin Shi Huang": "Q7192",
    "Himiko": "Q156440",

    # Avenger
    "Edmond Dantes": "Q1338702",
    "Jeanne d'Arc (Alter)": None,
    "Angra Mainyu": "Q267918",
    "Gorgon": "Q38143",
    "Antonio Salieri": "Q51088",

    # Foreigner
    "Abigail Williams": "Q2975376",
    "Hokusai": "Q5586",
    "Yang Guifei": "Q236106",
    "Van Gogh": "Q5582",
}


HEADERS = {
    "User-Agent": "ChaldeasBot/1.0 (https://chaldeas.site; contact@chaldeas.site)"
}


def get_wikidata_info(qid: str) -> dict:
    """Wikidata에서 엔티티 정보 가져오기"""
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


def import_servants():
    """서번트 QID를 DB에 추가"""
    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor()

    # Get unique QIDs
    qids = set(v for v in SERVANT_QIDS.values() if v)
    print(f"Total unique QIDs: {len(qids)}")

    added = 0
    already_exists = 0
    failed = []

    for qid in sorted(qids):
        # Check if exists
        cur.execute("SELECT id, name FROM persons WHERE wikidata_id = %s", (qid,))
        existing = cur.fetchone()

        if existing:
            already_exists += 1
            continue

        # Fetch from Wikidata
        info = get_wikidata_info(qid)
        if not info or not info["name"]:
            failed.append(qid)
            print(f"  {qid} - FAILED")
            continue

        # Generate slug from name
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', info["name"].lower()).strip('-')
        # Make sure slug is unique by adding QID
        slug = f"{slug}-{info['wikidata_id'].lower()}"

        try:
            cur.execute("""
                INSERT INTO persons (wikidata_id, name, name_ko, slug, biography, birth_year, death_year, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (
                info["wikidata_id"],
                info["name"],
                info["name_ko"],
                slug,
                info["description"],  # maps to biography column
                info["birth_year"],
                info["death_year"]
            ))
            new_id = cur.fetchone()[0]
            conn.commit()
            print(f"  {qid} -> {info['name']} (id={new_id})")
            added += 1
        except Exception as e:
            conn.rollback()
            failed.append(qid)
            print(f"  {qid} - DB ERROR: {e}")

        time.sleep(0.3)

    conn.close()

    print(f"\n=== Summary ===")
    print(f"Already in DB: {already_exists}")
    print(f"Added: {added}")
    print(f"Failed: {len(failed)}")

    return added, failed


def fix_wrong_qid_mappings():
    """잘못된 QID 연결 수정"""
    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor()

    # Q41620 (잘못됨: Anastasius II) -> 이건 원래 다른 인물
    # Gilgamesh는 Q159709
    cur.execute("SELECT id, name, wikidata_id FROM persons WHERE wikidata_id = 'Q41620'")
    wrong = cur.fetchone()
    if wrong:
        print(f"Found wrong QID Q41620: {wrong[1]} (id={wrong[0]})")
        # 이건 실제로 Anastasius II가 맞을 수 있음. QID 제거
        cur.execute("UPDATE persons SET wikidata_id = NULL WHERE id = %s", (wrong[0],))
        conn.commit()
        print("  Removed QID from Anastasius II")

    # Q43718 (잘못됨: Nikolai Gogol) -> Vlad III
    cur.execute("SELECT id, name, wikidata_id FROM persons WHERE wikidata_id = 'Q43718'")
    wrong = cur.fetchone()
    if wrong:
        print(f"Found wrong QID Q43718: {wrong[1]} (id={wrong[0]})")
        # 이것도 원래 인물의 QID가 잘못 입력된 것
        cur.execute("UPDATE persons SET wikidata_id = NULL WHERE id = %s", (wrong[0],))
        conn.commit()
        print("  Removed QID from Nikolai Gogol")

    conn.close()


if __name__ == "__main__":
    print("=== Fixing wrong QID mappings ===")
    fix_wrong_qid_mappings()

    print("\n=== Importing servants ===")
    import_servants()
