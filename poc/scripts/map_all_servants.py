"""
모든 FGO 서번트를 DB persons와 매핑
- 변형(Alter, Lily, Summer 등)은 기본 인물과 같은 QID 사용
- Verified Wikidata QIDs
"""
import json
import re
import psycopg2
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# 이미 확인된 QID 매핑 (verified_servant_qids.json에서)
VERIFIED_QIDS = {}

# 완전한 수동 매핑 - VERIFIED QIDs only
MANUAL_QIDS = {
    # === 아서왕 전설 (Arthurian) ===
    "Altria Pendragon": "Q45792",  # King Arthur
    "Altria Pendragon Alter": "Q45792",
    "Altria Caster": "Q45792",
    "Arthur Pendragon": "Q45792",
    "Arthur Pendragon (Prototype)": "Q45792",
    "Artoria": "Q45792",
    "Arturia": "Q45792",
    "Altria": "Q45792",
    "Saber Lily": "Q45792",
    "Mordred": "Q81109",
    "Gawain": "Q831685",
    "Lancelot": "Q215681",
    "Bedivere": "Q202529",
    "Tristan": "Q164136",
    "Merlin": "Q188044",

    # === 니벨룽겐 (Nibelungenlied) ===
    "Siegfried": "Q131554",
    "Sigurd": "Q223688",
    "Kriemhild": "Q543379",
    "Brynhildr": "Q850506",

    # === 그리스 신화 (Greek Mythology) ===
    "Heracles": "Q122248",
    "Achilles": "Q41746",
    "Hector": "Q168395",
    "Paris": "Q188702",
    "Medusa": "Q160730",
    "Euryale": "Q160730",
    "Stheno": "Q160730",
    "Atalante": "Q190323",
    "Atalanta": "Q190323",
    "Medea": "Q174278",
    "Circe": "Q187602",
    "Asterios": "Q129866",  # Minotaur
    "Chiron": "Q183417",
    "Jason": "Q43589",
    "Orion": "Q44520",
    "Super Orion": "Q44520",
    "Artemis": "Q39503",
    "Europa": "Q131072",
    "Astraea": "Q202387",  # Astraea goddess
    "Caenis": "Q1132772",  # Caeneus
    "Penthesilea": "Q379828",
    "Asclepius": "Q181602",
    "Odysseus": "Q46841",
    "Dioscuri": "Q135296",

    # === 메소포타미아 (Mesopotamia) ===
    "Gilgamesh": "Q159709",
    "Enkidu": "Q463220",
    "Ishtar": "Q189246",
    "Ereshkigal": "Q654458",
    "Tiamat": "Q188441",

    # === 이집트 (Egypt) ===
    "Cleopatra": "Q635",
    "Ozymandias": "Q1523",  # Ramesses II
    "Nitocris": "Q265580",
    "Nefertari": "Q131761",

    # === 로마 (Roman) ===
    "Nero": "Q1413",
    "Nero Claudius": "Q1413",
    "Gaius Julius Caesar": "Q1048",
    "Julius Caesar": "Q1048",
    "Caligula": "Q1409",
    "Romulus": "Q2186",
    "Romulus=Quirinus": "Q2186",
    "Romulus-Quirinus": "Q2186",
    "Spartacus": "Q83406",
    "Boudica": "Q184634",

    # === 아일랜드/켈트 (Irish/Celtic) ===
    "Cu Chulainn": "Q211955",
    "Cú Chulainn": "Q211955",
    "Scathach": "Q930509",
    "Scáthach": "Q930509",
    "Scáthach-Skadi": "Q930509",
    "Diarmuid Ua Duibhne": "Q1209163",
    "Fionn mac Cumhaill": "Q382610",
    "Fergus mac Roich": "Q387800",
    "Fergus mac Róich": "Q387800",
    "Queen Medb": "Q1141828",
    "Medb": "Q1141828",
    "Manannan mac Lir": "Q1888724",
    "Manannan mac Lir (Bazett)": "Q1888724",

    # === 북유럽 (Norse) ===
    "Valkyrie": "Q131087",
    "Ortlinde": "Q131087",
    "Thrúd": "Q827758",
    "Skadi": "Q244032",
    "Skaði": "Q244032",

    # === 인도 (Indian) ===
    "Arjuna": "Q185790",
    "Arjuna Alter": "Q185790",
    "Karna": "Q2727397",
    "Rama": "Q188619",
    "Sita": "Q1137006",
    "Parvati": "Q170485",
    "Pārvatī": "Q170485",
    "Lakshmi Bai": "Q181878",
    "Ashwatthama": "Q2044550",
    "Aśvatthāman": "Q2044550",
    "Vritra": "Q797498",
    "Kama": "Q113155",  # Kamadeva
    "Ganesha": "Q188511",

    # === 중국 (Chinese) ===
    "Xuanzang Sanzang": "Q42063",
    "Xuanzang": "Q42063",
    "Qin Shi Huang": "Q7192",
    "Consort Yu": "Q3275211",
    "Yu Mei-ren": "Q3275211",
    "Qin Liangyu": "Q276728",
    "Chen Gong": "Q707622",
    "Xiang Yu": "Q83410",
    "Jing Ke": "Q532410",
    "Li Shuwen": "Q697515",
    "Nezha": "Q1207659",
    "Yan Qing": "Q836134",
    "Red Hare": "Q1321898",
    "Lu Bu Fengxian": "Q317846",
    "Lu Bu": "Q317846",
    "Taigong Wang": "Q701488",  # Jiang Ziya
    "Prince of Lan Ling": "Q710336",  # Gao Changgong
    "Wu Zetian": "Q9738",
    "Yang Guifei": "Q298046",
    "Taisui Xingjun": "Q2994191",
    "Daikokuten": "Q1759916",

    # === 일본 (Japanese) ===
    "Miyamoto Musashi": "Q193344",
    "Okita Souji": "Q267549",
    "Okita Soji": "Q267549",
    "Hijikata Toshizo": "Q701182",
    "Saito Hajime": "Q138256",
    "Oda Nobunaga": "Q171411",
    "Oda Nobukatsu": "Q3044815",
    "Demon King Nobunaga": "Q171411",
    "Minamoto-no-Raikou": "Q590523",
    "Ushiwakamaru": "Q310445",
    "Tomoe Gozen": "Q170526",
    "Musashibou Benkei": "Q316898",
    "Sasaki Kojirou": "Q549737",
    "Sasaki Kojiro": "Q549737",
    "Fuuma Kotarou": "Q1368291",
    "Fuuma \"Evil-wind\" Kotarou": "Q1368291",
    "Shuten-Douji": "Q986527",
    "Shuten-douji": "Q986527",
    "Ibaraki-Douji": "Q5983716",
    "Ibaraki-douji": "Q5983716",
    "Ibuki-Douji": "Q986527",  # Related to Shuten
    "Kiyohime": "Q1207544",
    "Murasaki Shikibu": "Q81731",
    "Sei Shounagon": "Q231603",
    "Sei Shonagon": "Q231603",
    "Taira-no-Kagekiyo": "Q7676361",
    "Sakata Kintoki": "Q1047529",
    "Watanabe-no-Tsuna": "Q6582069",
    "Tawara Touta": "Q1136623",  # Fujiwara no Hidesato
    "Mochizuki Chiyome": "Q1085443",
    "Katou Danzo": "Q6378605",
    "Katou \"Black Kite\" Danzo": "Q6378605",
    "Houzouin Inshun": "Q10490430",
    "Yagyu Munenori": "Q631099",
    "Yagyu Tajima-no-kami Munenori": "Q631099",
    "Sakamoto Ryouma": "Q312264",
    "Nagao Kagetora": "Q704640",
    "Takeda Harunobu": "Q276404",  # Takeda Shingen
    "Takeda Shingen": "Q276404",
    "Mori Nagayoshi": "Q1071391",
    "Izumo-no-Okuni": "Q1334304",
    "Sei": "Q231603",
    "Minamoto-no-Tametomo": "Q1339356",
    "Kiichi Hogen": "Q11673397",
    "Kyokutei Bakin": "Q463142",
    "Okada Izo": "Q3058220",
    "Sen-no-Rikyu": "Q305477",
    "Amakusa Shirou": "Q452628",
    "Amakusa Shiro": "Q452628",
    "Himiko": "Q234451",
    "Katsushika Hokusai": "Q5586",
    "Osakabehime": "Q17209288",
    "Beni-Enma": None,  # Yokai from folklore, no specific Wikidata entry

    # === 유럽 역사 (European History) ===
    "Joan of Arc": "Q7226",
    "Jeanne d'Arc": "Q7226",
    "Jeanne d'Arc Alter": "Q7226",
    "Jeanne d'Arc Alter Santa Lily": "Q7226",
    "Napoleon": "Q517",
    "Napoleon Bonaparte": "Q517",
    "Marie Antoinette": "Q47365",
    "Francis Drake": "Q36517",
    "Christopher Columbus": "Q7322",
    "Ivan the Terrible": "Q7996",
    "Anastasia": "Q157961",
    "Elizabeth Bathory": "Q170846",
    "Elisabeth Báthory": "Q170846",
    "Carmilla": "Q170846",
    "Vlad III": "Q43715",
    "Gilles de Rais": "Q311634",
    "Edward Teach": "Q213518",  # Blackbeard
    "Blackbeard": "Q213518",
    "Anne Bonny & Mary Read": "Q231549",
    "Chevalier d'Eon": "Q715027",
    "Charlotte Corday": "Q216063",
    "Wolfgang Amadeus Mozart": "Q254",
    "Antonio Salieri": "Q51088",
    "Hans Christian Andersen": "Q5673",
    "Leonardo da Vinci": "Q762",
    "Florence Nightingale": "Q37103",
    "Nikola Tesla": "Q9036",
    "Thomas Edison": "Q8743",
    "Charles Babbage": "Q29231",
    "Helena Blavatsky": "Q170746",
    "Bartholomew Roberts": "Q205691",
    "Bradamante": "Q1163427",
    "Mandricardo": "Q53997876",
    "Phantom of the Opera": "Q1346515",
    "James Moriarty": "Q283111",
    "Sherlock Holmes": "Q4653",
    "Henry Jekyll & Hyde": "Q180377",
    "Dobrynya Nikitich": "Q1319851",
    "Calamity Jane": "Q235649",
    "Kōnstantînos XI": "Q37142",
    "Ptolemaîos": "Q168261",
    "Hephaistíon": "Q310739",
    "Paracelsus": "Q83428",
    "Paracelsus von Hohenheim": "Q83428",
    "Avicebron": "Q239355",  # Solomon ibn Gabirol
    "Darius III": "Q130650",
    "Leonidas I": "Q44228",
    "Robin Hood": "Q122634",
    "Alexander the Great": "Q8409",
    "Alexander": "Q8409",
    "Iskandar": "Q8409",
    "Attila the Hun": "Q36724",
    "Attila": "Q36724",

    # === 베트남 (Vietnamese) ===
    "Hai Bà Trưng": "Q1207428",

    # === 미국 (American) ===
    "Abigail Williams": "Q118352128",
    "Paul Bunyan": "Q150519",
    "Calamity Jane": "Q235649",

    # === 아즈텍 (Aztec) ===
    "Quetzalcoatl": "Q2736568",

    # === 문학 캐릭터 (Literary Characters) ===
    "Edmond Dantes": "Q1952877",
    "Frankenstein": "Q150827",
    "Beowulf": "Q48328",
    "Jack the Ripper": "Q43963",
    "Scheherazade": "Q217410",
    "Nemo": "Q747589",
    "Captain Nemo": "Q747589",

    # === 동양 신화/전설 (Eastern Mythology) ===
    "Tamamo-no-Mae": "Q1327792",

    # === 힌두교 신 (Hindu Deities) ===
    "Solomon": "Q37085",
    "David": "Q41370",

    # === Vincent van Gogh ===
    "Vincent van Gogh": "Q5582",
    "Van Gogh": "Q5582",

    # === 페이트/타입문 오리지널 (TYPE-MOON Originals - No Real Counterpart) ===
    "Mash Kyrielight": None,
    "Emiya": None,
    "Emiya Alter": None,
    "EMIYA": None,
    "BB": None,
    "Meltryllis": None,
    "Passionlip": None,
    "Kingprotea": None,
    "Violet": None,
    "Kazuradrop": None,
    "Sessyoin Kiara": None,
    "Jinako Carigiri": None,
    "Chloe von Einzbern": None,
    "Illyasviel von Einzbern": None,
    "Miyu Edelfelt": None,
    "Ryougi Shiki": None,
    "Asagami Fujino": None,
    "Mysterious Heroine X": None,
    "Mysterious Heroine XX": None,
    "Mysterious Heroine X Alter": None,
    "Mysterious Alter Ego Λ": None,
    "Mysterious Idol X": None,
    "Mysterious Ranmaru X": None,
    "Space Ishtar": None,
    "First Hassan": None,
    "\"First Hassan\"": None,
    "Hassan of the Cursed Arm": None,
    "Hassan of the Hundred Personas": None,
    "Hassan of the Serenity": None,
    "Tamamo Cat": None,
    "Koyanskaya of Light": None,
    "Koyanskaya of Dark": None,
    "Tamamo Vitch Koyanskaya": None,
    "Voyager": None,
    "Hessian Lobo": None,
    "Sitonai": None,
    "Mecha Eli-chan": None,
    "Mecha Eli-chan Mk.II": None,
    "Okita Souji Alter": None,
    "Super Bunyan": None,
    "Attila the San": None,
    "Archetype: EARTH": None,
    "Lady Avalon": None,
    "Goetia": None,
    "Beast III/R": None,
    "Beast III/L": None,
    "Beast IV": None,
    "Habetrot": None,
    "Miss Crane": None,
    "Baobhan Sith": None,
    "Utsumi Erice": None,
    "Ashiya Douman": None,
    "Senji Muramasa": None,
    "Kotomine Kirei": None,
    "Anastasia & Viy": None,
    "Aŋra Mainiiu": None,
    "Nursery Rhyme": None,
    "Irisviel": None,
    "Irisviel von Einzbern": None,
    "Illyasviel": None,
    "Chloe": None,
    "Bunny Artoria": None,
    "Shiki Ryougi": None,
    "Fujino Asagami": None,
    "Kijyo Koyo": None,
}


def load_verified_qids():
    """Load previously verified QIDs"""
    global VERIFIED_QIDS
    path = PROJECT_ROOT / "data/raw/atlas_academy/verified_servant_qids.json"
    if path.exists():
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
            VERIFIED_QIDS = {k: v['qid'] for k, v in data['verified'].items()}


def normalize_name(name):
    """Normalize servant name for matching"""
    name = re.sub(r'\s*\([^)]*\)\s*', '', name)  # Remove (Alter), (Lily), etc.
    name = name.strip()
    return name


def map_all_servants():
    """Map all servants to DB"""
    load_verified_qids()

    # Load servants
    with open(PROJECT_ROOT / "data/raw/atlas_academy/fgo_historical_figures.json", encoding='utf-8') as f:
        servants = json.load(f)

    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor()

    results = {
        "mapped": [],
        "fgo_original": [],
        "not_found": [],
    }

    for s in servants:
        fgo_name = s['fgo_name']
        base_name = normalize_name(fgo_name)

        # 1. Check manual mappings first
        qid = MANUAL_QIDS.get(fgo_name) or MANUAL_QIDS.get(base_name)

        # 2. Check verified QIDs
        if qid is None and fgo_name not in MANUAL_QIDS and base_name not in MANUAL_QIDS:
            qid = VERIFIED_QIDS.get(fgo_name) or VERIFIED_QIDS.get(base_name)

        # 3. If explicitly None in manual, it's FGO original
        if fgo_name in MANUAL_QIDS and MANUAL_QIDS[fgo_name] is None:
            results["fgo_original"].append(fgo_name)
            continue
        if base_name in MANUAL_QIDS and MANUAL_QIDS[base_name] is None:
            results["fgo_original"].append(fgo_name)
            continue

        # 4. Try to find in DB by QID
        if qid:
            cur.execute("SELECT id, name FROM persons WHERE wikidata_id = %s", (qid,))
            person = cur.fetchone()
            if person:
                results["mapped"].append({
                    "fgo_name": fgo_name,
                    "qid": qid,
                    "person_id": person[0],
                    "person_name": person[1]
                })
                continue

        # 5. Try name-based search in DB
        cur.execute("""
            SELECT id, name, wikidata_id FROM persons
            WHERE LOWER(name) = LOWER(%s) OR LOWER(name) LIKE LOWER(%s)
            LIMIT 1
        """, (base_name, f"%{base_name}%"))
        person = cur.fetchone()
        if person:
            results["mapped"].append({
                "fgo_name": fgo_name,
                "qid": person[2],
                "person_id": person[0],
                "person_name": person[1]
            })
            continue

        # Not found
        results["not_found"].append({
            "fgo_name": fgo_name,
            "base_name": base_name,
            "origin": s.get("origin", "Unknown")
        })

    conn.close()

    # Save results
    output_path = PROJECT_ROOT / "data/raw/atlas_academy/servant_db_mapping.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"=== Mapping Results ===")
    print(f"Mapped to DB: {len(results['mapped'])}")
    print(f"FGO Original: {len(results['fgo_original'])}")
    print(f"Not Found: {len(results['not_found'])}")

    # Save not found list
    if results['not_found']:
        not_found_path = PROJECT_ROOT / "poc/data/not_found_servants.txt"
        with open(not_found_path, 'w', encoding='utf-8') as f:
            f.write(f"Unique base names not found: {len(set(item['base_name'] for item in results['not_found']))}\n\n")
            for item in results['not_found']:
                f.write(f"{item['fgo_name']} | base: {item['base_name']} | origin: {item['origin']}\n")
        print(f"Not found list saved to: {not_found_path}")

    return results


if __name__ == "__main__":
    map_all_servants()
