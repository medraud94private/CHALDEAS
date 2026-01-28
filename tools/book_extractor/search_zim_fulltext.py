"""
Gutenberg ZIM 전체 텍스트 검색으로 FGO 서번트 관련 책 찾기
"""
import json
from pathlib import Path
from collections import defaultdict

from libzim.reader import Archive
from libzim.search import Query, Searcher

PROJECT_ROOT = Path(__file__).parent.parent.parent
ZIM_PATH = PROJECT_ROOT / "data" / "kiwix" / "gutenberg_en_all.zim"
OUTPUT_FILE = Path(__file__).parent / "zim_search_results.json"

# 서번트별 검색 키워드 (titles/authors to search for)
SEARCH_QUERIES = {
    # Greek/Troy
    "Achilles": ["iliad homer", "achilles"],
    "Hector": ["iliad homer", "hector troy"],
    "Odysseus": ["odyssey homer", "ulysses"],
    "Circe": ["odyssey homer", "circe"],
    "Jason": ["argonautica", "jason golden fleece"],
    "Medea": ["medea euripides"],
    "Heracles": ["hercules", "twelve labors hercules"],
    "Perseus": ["perseus"],
    "Theseus": ["theseus minotaur"],
    "Orion": ["orion mythology"],
    "Medusa": ["medusa gorgon", "perseus medusa"],

    # Mesopotamia
    "Gilgamesh": ["gilgamesh epic", "gilgamesh"],
    "Enkidu": ["gilgamesh"],
    "Ishtar": ["ishtar", "babylonian"],

    # India
    "Arjuna": ["mahabharata", "arjuna"],
    "Karna": ["mahabharata", "karna"],
    "Rama": ["ramayana", "rama"],

    # Celtic
    "Cu Chulainn": ["cuchulain", "ulster cycle", "tain bo cuailnge"],
    "Scathach": ["cuchulain"],
    "Fionn": ["ossian", "fionn", "finn"],
    "Diarmuid": ["diarmuid", "pursuit"],
    "Medb": ["tain bo", "queen medb"],

    # Norse
    "Siegfried": ["nibelungenlied", "siegfried"],
    "Sigurd": ["volsung", "sigurd"],
    "Brynhild": ["volsung", "brunhild", "brynhild"],
    "Beowulf": ["beowulf"],

    # Arthurian
    "Artoria": ["king arthur", "morte darthur", "camelot"],
    "Lancelot": ["lancelot"],
    "Tristan": ["tristan isolde", "tristram"],
    "Gawain": ["gawain green knight"],
    "Mordred": ["morte darthur", "mordred"],
    "Merlin": ["merlin"],
    "Galahad": ["galahad holy grail"],
    "Percival": ["parsifal", "percival"],
    "Morgan": ["morgan le fay"],

    # Charlemagne
    "Charlemagne": ["charlemagne", "carolingian"],
    "Roland": ["song roland", "chanson roland"],
    "Astolfo": ["orlando furioso"],

    # Roman
    "Caesar": ["julius caesar", "caesar"],
    "Nero": ["nero emperor"],
    "Spartacus": ["spartacus"],
    "Boudica": ["boudica", "boudicca"],

    # Egyptian
    "Ozymandias": ["ramesses", "ozymandias shelley"],
    "Cleopatra": ["cleopatra"],
    "Nitocris": ["nitocris"],

    # Persian/Arabian
    "Scheherazade": ["arabian nights", "thousand one nights"],
    "Darius": ["darius persia", "persian wars"],

    # Biblical
    "David": ["david goliath", "king david"],
    "Solomon": ["king solomon", "solomon wisdom"],
    "Salome": ["salome wilde", "salome herod"],

    # Literature
    "Sherlock Holmes": ["sherlock holmes conan doyle"],
    "Moriarty": ["sherlock holmes"],
    "Frankenstein": ["frankenstein shelley"],
    "Phantom": ["phantom opera leroux"],
    "Jekyll": ["jekyll hyde stevenson"],
    "Edmond Dantes": ["monte cristo dumas"],
    "Don Quixote": ["don quixote cervantes"],
    "Andersen": ["hans andersen fairy"],
    "Shakespeare": ["shakespeare"],
    "Dante": ["divine comedy dante", "inferno dante"],

    # Historical
    "Napoleon": ["napoleon biography", "napoleon"],
    "Marie Antoinette": ["marie antoinette"],
    "Jeanne d'Arc": ["joan arc"],
    "Leonardo": ["leonardo vinci"],
    "Alexander": ["alexander great", "alexander macedon"],
    "Leonidas": ["thermopylae", "sparta"],
    "Vlad": ["dracula", "vlad impaler"],

    # Chinese
    "Lu Bu": ["three kingdoms", "romance three kingdoms"],
    "Zhuge Liang": ["three kingdoms"],
    "Xuanzang": ["journey west", "tripitaka"],

    # Japanese
    "Musashi": ["musashi miyamoto", "book five rings"],

    # Pirates
    "Drake": ["francis drake"],
    "Blackbeard": ["blackbeard", "pirates"],
    "Anne Bonny": ["anne bonny", "mary read"],

    # American
    "Geronimo": ["geronimo apache"],
    "Billy the Kid": ["billy kid"],
    "Edison": ["thomas edison"],
    "Tesla": ["nikola tesla"],

    # Others
    "Robin Hood": ["robin hood"],
    "William Tell": ["william tell"],
    "Attila": ["attila hun"],
    "Florence Nightingale": ["florence nightingale"],

    # Mythology collections
    "Greek Myths": ["bulfinch mythology", "greek mythology", "ovid metamorphoses"],
    "Norse Myths": ["norse mythology", "edda"],
    "Celtic Myths": ["celtic mythology", "irish mythology"],
    "Egyptian Myths": ["egyptian mythology", "book dead egypt"],
}


def search_zim():
    """ZIM 파일에서 전체 텍스트 검색"""
    print(f"Opening ZIM: {ZIM_PATH}")
    zim = Archive(str(ZIM_PATH))
    print(f"Total entries: {zim.entry_count:,}")
    print(f"Article count: {zim.article_count:,}")
    print(f"Has fulltext index: {zim.has_fulltext_index}")

    searcher = Searcher(zim)

    results = defaultdict(list)
    all_matches = {}

    print(f"\nSearching for {len(SEARCH_QUERIES)} servants with various queries...")
    print("=" * 60)

    for servant, queries in SEARCH_QUERIES.items():
        servant_matches = []

        for query_str in queries:
            query = Query().set_query(query_str)
            search = searcher.search(query)

            # Get up to 30 results per query
            count = min(search.getEstimatedMatches(), 30)
            if count == 0:
                continue

            result_set = search.getResults(0, count)

            for path in result_set:
                if path not in all_matches:
                    try:
                        entry = zim.get_entry_by_path(path)
                        title = entry.title
                        all_matches[path] = {
                            "title": title,
                            "path": path
                        }
                    except:
                        continue

                if path not in [m["path"] for m in servant_matches]:
                    servant_matches.append({
                        "title": all_matches[path]["title"],
                        "path": path,
                        "query": query_str
                    })

        if servant_matches:
            results[servant] = servant_matches
            print(f"  {servant:25}: {len(servant_matches)} books found")

    # Sort by number of matches
    sorted_results = dict(sorted(results.items(), key=lambda x: -len(x[1])))

    # Build output
    output = {
        "summary": {
            "total_servants_searched": len(SEARCH_QUERIES),
            "servants_with_matches": len(sorted_results),
            "total_unique_books": len(all_matches)
        },
        "by_servant": sorted_results,
        "all_books": list(all_matches.values())[:500]
    }

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"Total unique books found: {len(all_matches)}")
    print(f"Servants with matches: {len(sorted_results)}")

    # Top 20 summary
    print("\n" + "=" * 60)
    print("TOP 20 SERVANTS BY BOOK COUNT")
    print("=" * 60)
    for i, (servant, books) in enumerate(list(sorted_results.items())[:20]):
        print(f"  {i+1:2}. {servant:25}: {len(books)} books")
        for book in books[:2]:
            print(f"        - {book['title'][:50]}")


if __name__ == "__main__":
    search_zim()
