"""
FGO 서번트 목록을 구텐베르크 ZIM과 대조하여 관련 책 찾기

Usage:
    python match_servants_to_gutenberg.py
"""
import json
import re
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVANTS_FILE = PROJECT_ROOT / "data" / "raw" / "atlas_academy" / "servants_basic_na.json"
ZIM_PATH = PROJECT_ROOT / "data" / "kiwix" / "gutenberg_en_all.zim"
OUTPUT_FILE = Path(__file__).parent / "servant_book_matches.json"

# 서번트 이름 → 검색 키워드 매핑 (역사적/신화적 이름)
SERVANT_KEYWORDS = {
    # 그리스/트로이
    "Achilles": ["achilles", "iliad", "trojan war", "patroclus"],
    "Hector": ["hector", "iliad", "trojan war", "troy"],
    "Paris": ["paris", "iliad", "helen of troy"],
    "Penthesilea": ["penthesilea", "amazon", "trojan war"],
    "Odysseus": ["odysseus", "ulysses", "odyssey", "homer"],
    "Circe": ["circe", "odyssey", "witch"],
    "Jason": ["jason", "argonaut", "golden fleece", "medea"],
    "Medea": ["medea", "argonaut", "jason", "colchis"],
    "Atalante": ["atalanta", "atalante", "argonaut", "arcadia"],
    "Heracles": ["hercules", "heracles", "twelve labors"],
    "Perseus": ["perseus", "medusa", "andromeda"],
    "Theseus": ["theseus", "minotaur", "ariadne", "athens"],
    "Orion": ["orion", "artemis", "hunter"],
    "Chiron": ["chiron", "centaur", "achilles teacher"],
    "Asclepius": ["asclepius", "aesculapius", "medicine god"],
    "Europa": ["europa", "zeus bull", "crete"],
    "Caenis": ["caenis", "caeneus", "poseidon"],
    "Dioscuri": ["castor", "pollux", "dioscuri", "gemini"],

    # 그리스 신/괴물
    "Medusa": ["medusa", "gorgon", "perseus"],
    "Euryale": ["euryale", "gorgon"],
    "Stheno": ["stheno", "gorgon"],
    "Asterios": ["asterios", "minotaur", "crete"],
    "Gorgon": ["gorgon", "medusa"],

    # 메소포타미아
    "Gilgamesh": ["gilgamesh", "uruk", "enkidu", "mesopotamia"],
    "Enkidu": ["enkidu", "gilgamesh", "clay"],
    "Ishtar": ["ishtar", "inanna", "babylon", "mesopotamia"],
    "Ereshkigal": ["ereshkigal", "underworld", "irkalla"],
    "Tiamat": ["tiamat", "chaos", "babylon"],

    # 인도
    "Arjuna": ["arjuna", "mahabharata", "pandava"],
    "Karna": ["karna", "mahabharata", "surya"],
    "Rama": ["rama", "ramayana", "sita", "ravana"],
    "Ashwatthama": ["ashwatthama", "drona", "mahabharata"],
    "Parvati": ["parvati", "shiva", "hindu goddess"],
    "Lakshmi Bai": ["lakshmi bai", "rani", "jhansi"],

    # 켈트
    "Cu Chulainn": ["cu chulainn", "cuchulain", "ulster", "setanta", "celtic"],
    "Scathach": ["scathach", "shadow land", "celtic warrior"],
    "Fergus mac Roich": ["fergus", "ulster", "celtic"],
    "Diarmuid Ua Duibhne": ["diarmuid", "fianna", "love spot"],
    "Fionn mac Cumhaill": ["fionn", "finn mccool", "fianna", "fenian"],
    "Medb": ["medb", "maeve", "connacht", "ulster"],

    # 북유럽
    "Siegfried": ["siegfried", "sigurd", "nibelungen", "fafnir"],
    "Sigurd": ["sigurd", "volsung", "fafnir", "brynhild"],
    "Brynhild": ["brynhild", "brunhild", "valkyrie", "sigurd"],
    "Valkyrie": ["valkyrie", "odin", "valhalla"],
    "Beowulf": ["beowulf", "grendel", "hrothgar"],
    "Eric Bloodaxe": ["eric bloodaxe", "viking", "norway"],

    # 아서왕
    "Altria Pendragon": ["arthur", "king arthur", "excalibur", "camelot"],
    "Lancelot": ["lancelot", "round table", "guinevere"],
    "Tristan": ["tristan", "isolde", "iseult", "cornwall"],
    "Gawain": ["gawain", "green knight", "round table"],
    "Mordred": ["mordred", "camlann", "round table"],
    "Bedivere": ["bedivere", "excalibur", "round table"],
    "Merlin": ["merlin", "wizard", "arthur"],
    "Galahad": ["galahad", "holy grail", "round table"],
    "Percival": ["percival", "grail", "round table"],
    "Gareth": ["gareth", "round table", "lynette"],
    "Morgan": ["morgan le fay", "morgana", "avalon"],

    # 샤를마뉴
    "Charlemagne": ["charlemagne", "carolingian", "roland"],
    "Roland": ["roland", "chanson", "charlemagne", "roncevaux"],
    "Astolfo": ["astolfo", "orlando furioso", "paladin"],
    "Bradamante": ["bradamante", "orlando furioso", "ruggiero"],

    # 로마
    "Romulus": ["romulus", "remus", "rome foundation"],
    "Julius Caesar": ["julius caesar", "caesar", "rubicon", "rome"],
    "Nero Claudius": ["nero", "roman emperor", "rome"],
    "Caligula": ["caligula", "roman emperor"],
    "Spartacus": ["spartacus", "gladiator", "slave revolt"],
    "Boudica": ["boudica", "boudicca", "iceni", "britain"],

    # 이집트
    "Ozymandias": ["ramesses", "ozymandias", "egypt pharaoh"],
    "Nitocris": ["nitocris", "egypt queen", "pharaoh"],
    "Cleopatra": ["cleopatra", "egypt", "ptolemy"],

    # 문학
    "Sherlock Holmes": ["sherlock holmes", "conan doyle", "detective"],
    "James Moriarty": ["moriarty", "professor", "sherlock"],
    "Frankenstein": ["frankenstein", "mary shelley", "monster"],
    "Phantom": ["phantom opera", "erik", "gaston leroux"],
    "Jekyll": ["jekyll", "hyde", "stevenson"],
    "Edmond Dantes": ["monte cristo", "dantes", "dumas"],
    "Don Quixote": ["don quixote", "cervantes", "sancho"],
    "Hans Andersen": ["hans andersen", "fairy tales", "denmark"],
    "Shakespeare": ["shakespeare", "hamlet", "macbeth", "othello"],
    "Dante": ["dante alighieri", "divine comedy", "inferno"],

    # 역사
    "Napoleon": ["napoleon", "bonaparte", "waterloo"],
    "Marie Antoinette": ["marie antoinette", "french revolution", "versailles"],
    "Jeanne d'Arc": ["joan of arc", "jeanne darc", "orleans", "maid"],
    "Leonardo da Vinci": ["leonardo", "da vinci", "renaissance"],
    "Iskandar": ["alexander", "great", "macedon", "persia"],
    "Darius III": ["darius", "persia", "achaemenid"],
    "Leonidas": ["leonidas", "sparta", "thermopylae", "300"],
    "Cleopatra": ["cleopatra", "egypt", "antony", "caesar"],
    "Vlad III": ["vlad", "dracula", "impaler", "wallachia"],
    "Ivan the Terrible": ["ivan", "terrible", "tsar", "russia"],
    "Qin Shi Huang": ["qin shi huang", "first emperor", "china"],
    "Wu Zetian": ["wu zetian", "empress", "tang", "china"],
    "Miyamoto Musashi": ["musashi", "miyamoto", "five rings", "samurai"],
    "Oda Nobunaga": ["nobunaga", "oda", "sengoku"],
    "Francis Drake": ["francis drake", "privateer", "armada"],
    "Edward Teach": ["blackbeard", "edward teach", "pirate"],
    "Anne Bonny": ["anne bonny", "mary read", "pirate"],
    "Columbus": ["columbus", "christopher", "america discovery"],
    "Geronimo": ["geronimo", "apache", "native american"],
    "Billy the Kid": ["billy kid", "outlaw", "wild west"],
    "Calamity Jane": ["calamity jane", "wild west", "deadwood"],
    "Florence Nightingale": ["florence nightingale", "nurse", "crimea"],
    "Nikola Tesla": ["nikola tesla", "electricity", "inventor"],
    "Thomas Edison": ["thomas edison", "inventor", "electric"],

    # 동양
    "Xuanzang": ["xuanzang", "journey west", "tripitaka"],
    "Lu Bu": ["lu bu", "three kingdoms", "red hare"],
    "Zhuge Liang": ["zhuge liang", "kongming", "three kingdoms"],
    "Scheherazade": ["scheherazade", "arabian nights", "thousand one nights"],
    "Queen of Sheba": ["queen sheba", "solomon", "ethiopia"],
    "Semiramis": ["semiramis", "assyria", "babylon queen"],

    # 성경
    "David": ["king david", "goliath", "psalms", "israel"],
    "Solomon": ["king solomon", "wisdom", "temple", "sheba"],
    "Martha": ["martha", "bethany", "lazarus", "bible"],
    "Salome": ["salome", "john baptist", "herod"],
    "Abigail Williams": ["abigail williams", "salem witch", "massachusetts"],

    # 아즈텍/마야
    "Quetzalcoatl": ["quetzalcoatl", "feathered serpent", "aztec"],
    "Jaguar Warrior": ["jaguar warrior", "aztec", "mesoamerica"],

    # 러시아
    "Anastasia": ["anastasia", "romanov", "russia"],

    # 일본 서번트는 일본어 자료가 더 적합
}


def load_servants():
    """FGO 서번트 목록 로드"""
    with open(SERVANTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    servants = []
    seen = set()

    for s in data:
        name = s.get('name', '')
        # 기본 이름 (괄호 전)
        base_name = name.split('(')[0].strip()

        if base_name and base_name not in seen:
            seen.add(base_name)
            servants.append({
                'name': base_name,
                'full_name': name,
                'class': s.get('className', ''),
                'rarity': s.get('rarity', 0)
            })

    return servants


def search_gutenberg_zim(keywords: list) -> list:
    """구텐베르크 ZIM에서 키워드로 책 검색"""
    try:
        from libzim.reader import Archive
    except ImportError:
        print("libzim not installed. Run: pip install libzim")
        return []

    if not ZIM_PATH.exists():
        print(f"ZIM file not found: {ZIM_PATH}")
        return []

    zim = Archive(str(ZIM_PATH))
    matches = []

    for entry in zim:
        if entry.is_redirect:
            continue

        title = entry.title.lower()

        # 키워드 매칭
        for kw in keywords:
            if kw.lower() in title:
                matches.append({
                    'title': entry.title,
                    'path': entry.path,
                    'matched_keyword': kw
                })
                break

    return matches


def main():
    print("=" * 70)
    print("FGO Servant → Gutenberg Book Matching")
    print("=" * 70)

    # 서번트 로드
    print("\n[1/3] Loading FGO servants...")
    servants = load_servants()
    print(f"  Loaded {len(servants)} unique servants")

    # 결과 저장용
    results = {
        'matched': [],      # 키워드 매핑이 있고 ZIM에서 책을 찾은 서번트
        'has_keywords': [], # 키워드 매핑은 있지만 ZIM 검색 안함/못함
        'no_keywords': []   # 키워드 매핑이 없는 서번트 (주로 FGO 오리지널)
    }

    print("\n[2/3] Categorizing servants...")
    for servant in servants:
        name = servant['name']

        # 키워드 매핑 확인
        keywords = None
        for key, kws in SERVANT_KEYWORDS.items():
            if key.lower() in name.lower() or name.lower() in key.lower():
                keywords = kws
                break

        if keywords:
            results['has_keywords'].append({
                'servant': servant,
                'keywords': keywords
            })
        else:
            results['no_keywords'].append(servant)

    print(f"  With keywords: {len(results['has_keywords'])}")
    print(f"  Without keywords: {len(results['no_keywords'])}")

    # 결과 저장
    print("\n[3/3] Saving results...")

    output = {
        'summary': {
            'total_servants': len(servants),
            'with_keywords': len(results['has_keywords']),
            'without_keywords': len(results['no_keywords'])
        },
        'servants_with_keywords': results['has_keywords'],
        'servants_without_keywords': results['no_keywords'],
        'keyword_mapping': SERVANT_KEYWORDS
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Saved to: {OUTPUT_FILE}")

    # 요약 출력
    print("\n" + "=" * 70)
    print("SERVANTS WITH BOOK KEYWORDS")
    print("=" * 70)

    for item in results['has_keywords'][:30]:
        s = item['servant']
        kws = item['keywords'][:3]
        print(f"  {s['name']:30} → {', '.join(kws)}")

    if len(results['has_keywords']) > 30:
        print(f"  ... and {len(results['has_keywords']) - 30} more")

    print("\n" + "=" * 70)
    print("SERVANTS WITHOUT KEYWORDS (FGO Original / Need mapping)")
    print("=" * 70)

    for s in results['no_keywords'][:20]:
        print(f"  {s['name']}")

    if len(results['no_keywords']) > 20:
        print(f"  ... and {len(results['no_keywords']) - 20} more")


if __name__ == "__main__":
    main()
