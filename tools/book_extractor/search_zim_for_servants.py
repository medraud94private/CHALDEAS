"""
구텐베르크 ZIM에서 FGO 서번트 관련 책 전체 검색
"""
import json
import re
from pathlib import Path
from collections import defaultdict

try:
    from libzim.reader import Archive
    HAS_LIBZIM = True
except ImportError:
    HAS_LIBZIM = False
    print("libzim not installed. Run: pip install libzim")

PROJECT_ROOT = Path(__file__).parent.parent.parent
ZIM_PATH = PROJECT_ROOT / "data" / "kiwix" / "gutenberg_en_all.zim"
OUTPUT_FILE = Path(__file__).parent / "zim_search_results.json"

# 서번트별 검색 키워드 (핵심만)
SEARCH_KEYWORDS = {
    # 그리스/트로이
    "Achilles": ["achilles", "iliad"],
    "Hector": ["hector", "iliad", "troy"],
    "Paris": ["paris troy", "helen troy"],
    "Odysseus": ["odysseus", "ulysses", "odyssey"],
    "Circe": ["circe"],
    "Jason": ["jason argonaut", "golden fleece"],
    "Medea": ["medea", "euripides medea"],
    "Atalante": ["atalanta"],
    "Heracles": ["hercules", "heracles", "twelve labors"],
    "Perseus": ["perseus"],
    "Theseus": ["theseus", "minotaur"],
    "Orion": ["orion hunter"],
    "Chiron": ["chiron centaur"],
    "Europa": ["europa zeus"],
    "Medusa": ["medusa", "gorgon"],
    "Asterios": ["minotaur"],

    # 메소포타미아
    "Gilgamesh": ["gilgamesh"],
    "Enkidu": ["enkidu"],
    "Ishtar": ["ishtar", "inanna"],
    "Tiamat": ["tiamat"],

    # 인도
    "Arjuna": ["arjuna", "mahabharata"],
    "Karna": ["karna", "mahabharata"],
    "Rama": ["rama", "ramayana"],
    "Ashwatthama": ["ashwatthama"],

    # 켈트
    "Cu Chulainn": ["cuchulain", "cu chulainn", "ulster"],
    "Scathach": ["scathach"],
    "Fergus": ["fergus mac roich"],
    "Diarmuid": ["diarmuid", "dermot"],
    "Fionn": ["fionn", "finn mccool", "ossian"],
    "Medb": ["medb", "maeve", "queen connacht"],

    # 북유럽
    "Siegfried": ["siegfried", "nibelungen"],
    "Sigurd": ["sigurd", "volsung"],
    "Brynhild": ["brynhild", "brunhild"],
    "Valkyrie": ["valkyrie", "valhalla"],
    "Beowulf": ["beowulf"],
    "Eric Bloodaxe": ["eric bloodaxe"],

    # 아서왕
    "Arthur": ["king arthur", "arthur pendragon", "camelot"],
    "Lancelot": ["lancelot"],
    "Tristan": ["tristan", "tristram", "isolde"],
    "Gawain": ["gawain", "green knight"],
    "Mordred": ["mordred"],
    "Merlin": ["merlin"],
    "Galahad": ["galahad", "holy grail"],
    "Percival": ["percival", "parsifal"],
    "Morgan": ["morgan le fay", "morgana"],

    # 샤를마뉴
    "Charlemagne": ["charlemagne", "carolingian"],
    "Roland": ["roland", "chanson roland"],
    "Astolfo": ["astolfo", "orlando furioso"],

    # 로마
    "Romulus": ["romulus remus"],
    "Caesar": ["julius caesar", "caesar"],
    "Nero": ["nero emperor", "nero rome"],
    "Caligula": ["caligula"],
    "Spartacus": ["spartacus"],
    "Boudica": ["boudica", "boudicca"],

    # 이집트
    "Ozymandias": ["ramesses", "ozymandias"],
    "Nitocris": ["nitocris"],
    "Cleopatra": ["cleopatra"],

    # 페르시아
    "Arash": ["arash kamangir"],
    "Darius": ["darius persia"],
    "Scheherazade": ["scheherazade", "arabian nights", "thousand one nights"],

    # 성경
    "David": ["king david", "david goliath"],
    "Solomon": ["king solomon", "solomon wisdom"],
    "Martha": ["martha bible"],
    "Salome": ["salome herod"],

    # 문학
    "Sherlock Holmes": ["sherlock holmes"],
    "Moriarty": ["moriarty"],
    "Frankenstein": ["frankenstein"],
    "Phantom": ["phantom opera"],
    "Jekyll": ["jekyll hyde"],
    "Edmond Dantes": ["monte cristo"],
    "Don Quixote": ["don quixote", "quixote"],
    "Andersen": ["hans andersen"],
    "Shakespeare": ["shakespeare"],
    "Dante": ["dante inferno", "divine comedy"],

    # 역사
    "Napoleon": ["napoleon"],
    "Marie Antoinette": ["marie antoinette"],
    "Jeanne d'Arc": ["joan arc", "jeanne arc"],
    "Leonardo": ["leonardo vinci"],
    "Alexander": ["alexander great", "alexander macedon"],
    "Leonidas": ["leonidas sparta", "thermopylae"],
    "Vlad": ["vlad dracula", "vlad impaler", "dracula"],
    "Ivan": ["ivan terrible"],
    "Anastasia": ["anastasia romanov"],

    # 중국
    "Lu Bu": ["lu bu", "three kingdoms"],
    "Zhuge Liang": ["zhuge liang", "kongming"],
    "Qin Shi Huang": ["qin shi huang", "first emperor china"],
    "Wu Zetian": ["wu zetian"],
    "Xuanzang": ["xuanzang", "journey west", "tripitaka"],

    # 일본
    "Musashi": ["musashi", "miyamoto musashi"],
    "Nobunaga": ["nobunaga"],

    # 해적
    "Drake": ["francis drake"],
    "Blackbeard": ["blackbeard", "edward teach"],
    "Anne Bonny": ["anne bonny", "mary read"],

    # 미국
    "Geronimo": ["geronimo apache"],
    "Billy the Kid": ["billy kid"],
    "Paul Bunyan": ["paul bunyan"],
    "Edison": ["thomas edison"],
    "Tesla": ["nikola tesla"],

    # 아즈텍
    "Quetzalcoatl": ["quetzalcoatl"],

    # 기타
    "Robin Hood": ["robin hood"],
    "William Tell": ["william tell"],
    "Attila": ["attila hun"],
    "Florence Nightingale": ["florence nightingale"],
    "Paracelsus": ["paracelsus"],
    "Abigail Williams": ["salem witch"],
    "Jacques de Molay": ["templar", "molay"],
    "Zenobia": ["zenobia palmyra"],
}


def search_zim():
    """ZIM 파일에서 키워드 검색"""
    if not HAS_LIBZIM:
        print("libzim required!")
        return

    if not ZIM_PATH.exists():
        print(f"ZIM not found: {ZIM_PATH}")
        return

    print(f"Opening ZIM: {ZIM_PATH}")
    print(f"This may take a while for 207GB file...")

    zim = Archive(str(ZIM_PATH))
    print(f"Total entries: {zim.entry_count:,}")

    # 결과 저장
    results = defaultdict(list)
    all_books = []

    # 모든 키워드를 소문자로 준비
    all_keywords = set()
    keyword_to_servant = {}
    for servant, keywords in SEARCH_KEYWORDS.items():
        for kw in keywords:
            kw_lower = kw.lower()
            all_keywords.add(kw_lower)
            if kw_lower not in keyword_to_servant:
                keyword_to_servant[kw_lower] = []
            keyword_to_servant[kw_lower].append(servant)

    print(f"Searching for {len(all_keywords)} keywords...")
    print()

    count = 0
    matched = 0

    for entry in zim:
        count += 1

        if count % 10000 == 0:
            print(f"  Scanned {count:,} entries, found {matched} matches...")

        if entry.is_redirect:
            continue

        title = entry.title
        title_lower = title.lower()

        # 키워드 매칭
        for kw in all_keywords:
            if kw in title_lower:
                servants = keyword_to_servant[kw]
                for servant in servants:
                    results[servant].append({
                        "title": title,
                        "path": entry.path,
                        "keyword": kw
                    })
                matched += 1
                all_books.append({
                    "title": title,
                    "path": entry.path,
                    "matched_keyword": kw,
                    "servants": servants
                })
                break  # 한 책당 한 번만 매칭

    print(f"\nScan complete!")
    print(f"Total entries scanned: {count:,}")
    print(f"Total matches: {matched}")

    # 결과 정리
    output = {
        "summary": {
            "total_scanned": count,
            "total_matches": matched,
            "servants_with_matches": len([s for s, books in results.items() if books])
        },
        "by_servant": {k: v for k, v in sorted(results.items()) if v},
        "all_matches": all_books[:500]  # 상위 500개만
    }

    # 저장
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {OUTPUT_FILE}")

    # 요약 출력
    print("\n" + "=" * 60)
    print("TOP SERVANTS BY BOOK COUNT")
    print("=" * 60)

    sorted_servants = sorted(results.items(), key=lambda x: -len(x[1]))
    for servant, books in sorted_servants[:30]:
        if books:
            print(f"  {servant:25} : {len(books)} books")
            for book in books[:3]:
                print(f"      - {book['title'][:50]}")


if __name__ == "__main__":
    search_zim()
