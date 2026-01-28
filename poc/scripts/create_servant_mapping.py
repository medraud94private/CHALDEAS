"""
FGO 서번트 → DB persons 매핑 생성
"""
import json
import psycopg2
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# FGO 서번트 → Wikidata QID 매핑 (수작업 확인된 것)
SERVANT_QIDS = {
    # Saber
    "Altria Pendragon": "Q45556",  # King Arthur
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
    "Diarmuid Ua Duibhne": "Q1129108",  # Saber version

    # Archer
    "Gilgamesh": "Q41620",
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
    "Alexander": "Q8409",  # Iskandar
    "Medusa": "Q38143",
    "Boudica": "Q130746",
    "Francis Drake": "Q36517",
    "Achilles": "Q41746",
    "Ushiwakamaru": "Q189346",  # Minamoto no Yoshitsune
    "Ivan the Terrible": "Q7994",
    "Christopher Columbus": "Q7322",
    "Marie Antoinette": "Q47365",
    "Ozymandias": "Q1279",  # Ramesses II
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
    "Gilgamesh (Caster)": "Q41620",
    "Paracelsus": "Q83428",
    "Thomas Edison": "Q8743",
    "Helena Blavatsky": "Q179991",
    "Circe": "Q134762",
    "Scheherazade": "Q1186638",
    "Anastasia Nikolaevna": "Q159544",
    "Avicebron": "Q148629",  # Solomon ibn Gabirol

    # Assassin
    "Sasaki Kojiro": "Q1261989",
    "Stheno": "Q1265131",
    "Mata Hari": "Q36108",
    "Jack the Ripper": "Q46700",
    "Carmilla": "Q432294",  # Elizabeth Bathory
    "Shuten-douji": "Q2370889",
    "Cleopatra": "Q635",
    "Semiramis": "Q172847",
    "First Hassan": None,  # Fictional
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
    "Tamamo Cat": None,  # FGO original
    "Frankenstein": "Q150827",  # Frankenstein's monster
    "Beowulf": "Q180061",
    "Nightingale": "Q37103",  # Florence Nightingale
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
    "Edmond Dantes": "Q1338702",  # Fictional
    "Jeanne d'Arc (Alter)": None,  # FGO original
    "Angra Mainyu": "Q267918",
    "Gorgon": "Q38143",  # Medusa
    "Antonio Salieri": "Q51088",

    # Moon Cancer
    "BB": None,  # Fate/Extra original

    # Alter Ego
    "Meltryllis": None,  # Fate/Extra
    "Passionlip": None,  # Fate/Extra
    "Okita Alter": None,  # FGO original

    # Foreigner
    "Abigail Williams": "Q2975376",
    "Hokusai": "Q5586",  # Katsushika Hokusai
    "Yang Guifei": "Q236106",
    "Van Gogh": "Q5582",
}

def create_mapping():
    """Generate servant-to-person mapping"""

    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor()

    # Load FGO servants
    with open(PROJECT_ROOT / "data/raw/atlas_academy/fgo_historical_figures.json", encoding='utf-8') as f:
        servants = json.load(f)

    results = {
        "matched": [],
        "no_qid": [],
        "qid_not_in_db": [],
        "no_mapping": []
    }

    for servant in servants:
        fgo_name = servant["fgo_name"]
        base_name = fgo_name.split("(")[0].strip()

        # Check if we have a QID mapping
        qid = SERVANT_QIDS.get(fgo_name) or SERVANT_QIDS.get(base_name)

        if qid:
            # Look up in DB
            cur.execute(
                "SELECT id, name, name_ko, birth_year, death_year FROM persons WHERE wikidata_id = %s",
                (qid,)
            )
            person = cur.fetchone()

            if person:
                results["matched"].append({
                    "fgo_name": fgo_name,
                    "fgo_class": servant.get("class"),
                    "fgo_rarity": servant.get("rarity"),
                    "wikidata_id": qid,
                    "person_id": person[0],
                    "person_name": person[1],
                    "person_name_ko": person[2],
                    "birth_year": person[3],
                    "death_year": person[4]
                })
            else:
                results["qid_not_in_db"].append({
                    "fgo_name": fgo_name,
                    "wikidata_id": qid
                })
        elif qid is None and fgo_name in SERVANT_QIDS:
            # Explicitly marked as no QID (FGO original)
            results["no_qid"].append({
                "fgo_name": fgo_name,
                "reason": "FGO original character"
            })
        else:
            results["no_mapping"].append({
                "fgo_name": fgo_name,
                "fgo_class": servant.get("class"),
                "origin": servant.get("origin")
            })

    conn.close()

    # Save results
    output_path = PROJECT_ROOT / "data/raw/atlas_academy/servant_person_mapping.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Results saved to {output_path}")
    print(f"\nSummary:")
    print(f"  Matched to DB: {len(results['matched'])}")
    print(f"  QID not in DB: {len(results['qid_not_in_db'])}")
    print(f"  No QID (FGO original): {len(results['no_qid'])}")
    print(f"  No mapping defined: {len(results['no_mapping'])}")

    return results

if __name__ == "__main__":
    create_mapping()
