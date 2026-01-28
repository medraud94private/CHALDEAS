"""
Search Wikidata for correct QIDs - version 2, simple name search
"""
import requests
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
HEADERS = {"User-Agent": "ChaldeasBot/1.0 (https://chaldeas.site)"}

# Names to search - ASCII friendly versions
NAMES_TO_SEARCH = [
    # Irish/Celtic
    "Diarmuid",
    "Fergus mac Roich",
    "Fionn mac Cumhaill",
    "Medb",
    "Manannan",
    "Scathach",

    # Japanese
    "Okita Soji",
    "Hijikata Toshizo",
    "Saito Hajime Shinsengumi",
    "Minamoto no Yorimitsu",
    "Benkei",
    "Fuma Kotaro",
    "Shuten-doji",
    "Ibaraki-doji",
    "Kiyohime",
    "Sei Shonagon",
    "Taira no Kagekiyo",
    "Kintaro folklore",
    "Watanabe no Tsuna",
    "Fujiwara no Hidesato",
    "Mochizuki Chiyome",
    "Kato Danzo ninja",
    "Hozoin Inshun",
    "Yagyu Munenori",
    "Oda Nobukatsu",
    "Minamoto no Tametomo",
    "Kyokutei Bakin",
    "Okada Izo",
    "Sen no Rikyu",
    "Izumo no Okuni",
    "Osakabe yokai",
    "Mori Nagayoshi",
    "Takeda Shingen",

    # Chinese
    "Consort Yu Xiang Yu",
    "Jing Ke assassin",
    "Li Shuwen martial arts",
    "Yan Qing Water Margin",
    "Red Hare horse",
    "Lu Bu warrior",
    "Jiang Ziya",
    "Gao Changgong Prince Lanling",
    "Taisui deity",
    "Daikokuten",

    # Greek/Mesopotamian
    "Minotaur mythology",
    "Astraea goddess",
    "Caeneus mythology",
    "Enkidu Gilgamesh",
    "Ereshkigal",

    # Indian
    "Parvati Hindu",
    "Lakshmi Bai Jhansi",
    "Ashwatthama Mahabharata",
    "Vritra dragon",
    "Kama Hindu god",

    # European
    "Chevalier d'Eon",
    "Blackbeard pirate Edward Teach",
    "Anne Bonny pirate",
    "Bradamante Orlando",
    "Mandricardo Orlando",
    "Professor Moriarty Holmes",
    "Constantine XI Palaiologos",
    "Ptolemy I Soter",
    "Hephaestion Alexander",
    "Solomon ibn Gabirol",
    "Kriemhild Nibelungen",
    "Abigail Williams Salem",
    "Trung Sisters Vietnam",
    "Valkyrie Norse",
    "Thrud Thor daughter",
    "Skadi Norse",
]


def search_wikidata(query):
    """Search Wikidata"""
    url = 'https://www.wikidata.org/w/api.php'
    params = {
        'action': 'wbsearchentities',
        'search': query,
        'language': 'en',
        'format': 'json',
        'limit': 5
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        results = r.json().get('search', [])
        return results
    except Exception as e:
        return []


def main():
    results = {}
    log_lines = []

    for name in NAMES_TO_SEARCH:
        search_results = search_wikidata(name)

        if search_results:
            best = search_results[0]
            results[name] = {
                "qid": best['id'],
                "label": best.get('label', ''),
                "description": best.get('description', ''),
            }
            log_lines.append(f"{name}: {best['id']} | {best.get('label', '')} | {best.get('description', '')[:80]}")
        else:
            results[name] = None
            log_lines.append(f"{name}: NOT FOUND")

        time.sleep(0.3)

    # Save results
    output_path = PROJECT_ROOT / "data/raw/atlas_academy/wikidata_qid_search_v2.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Save log
    log_path = PROJECT_ROOT / "poc/data/qid_search_log_v2.txt"
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    print(f"Found: {sum(1 for v in results.values() if v)}")
    print(f"Not found: {sum(1 for v in results.values() if not v)}")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
