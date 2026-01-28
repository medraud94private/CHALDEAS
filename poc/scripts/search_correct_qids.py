"""
Search Wikidata for correct QIDs for FGO servants
"""
import requests
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
HEADERS = {"User-Agent": "ChaldeasBot/1.0 (https://chaldeas.site)"}

# Names to search (from not_found list)
NAMES_TO_SEARCH = [
    # Irish/Celtic
    ("Diarmuid Ua Duibhne", "Irish mythology hero"),
    ("Fergus mac Róich", "Irish mythology Ulster Cycle"),
    ("Fionn mac Cumhaill", "Irish mythology Fenian Cycle"),
    ("Medb", "Irish mythology queen of Connacht"),
    ("Manannán mac Lir", "Irish sea god"),
    ("Scáthach", "Irish mythology warrior woman"),
    ("Cú Chulainn", "Irish mythology hero"),

    # Norse
    ("Valkyrie", "Norse mythology"),
    ("Thrúd", "Norse mythology Thor daughter"),
    ("Skaði", "Norse mythology winter goddess"),

    # Japanese historical/mythological
    ("Okita Sōji", "Shinsengumi captain"),
    ("Hijikata Toshizō", "Shinsengumi"),
    ("Saitō Hajime", "Shinsengumi"),
    ("Minamoto no Yorimitsu", "Heian samurai Raiko"),
    ("Benkei", "Japanese warrior monk"),
    ("Fūma Kotarō", "ninja"),
    ("Shuten-dōji", "Japanese oni"),
    ("Ibaraki-dōji", "Japanese oni"),
    ("Kiyohime", "Japanese legend dragon"),
    ("Sei Shōnagon", "Heian author"),
    ("Taira no Kagekiyo", "samurai Genpei"),
    ("Kintarō", "Japanese folklore"),
    ("Watanabe no Tsuna", "samurai Raiko"),
    ("Fujiwara no Hidesato", "Heian samurai"),
    ("Mochizuki Chiyome", "kunoichi"),
    ("Katō Danzō", "ninja"),
    ("Hōzōin Inshun", "monk spear"),
    ("Yagyū Munenori", "swordsman Tokugawa"),
    ("Oda Nobukatsu", "samurai Nobunaga brother"),
    ("Minamoto no Tametomo", "archer samurai"),
    ("Kyokutei Bakin", "Edo author"),
    ("Okada Izō", "bakumatsu hitokiri"),
    ("Sen no Rikyū", "tea master"),
    ("Izumo no Okuni", "kabuki founder"),
    ("Osakabe", "yokai himeji"),
    ("Mori Nagayoshi", "samurai sengoku"),
    ("Takeda Shingen", "daimyo sengoku"),

    # Chinese
    ("Yu Ji", "consort Xiang Yu"),
    ("Jing Ke", "assassin Qin"),
    ("Li Shuwen", "bajiquan master"),
    ("Yan Qing", "Water Margin"),
    ("Red Hare", "horse Three Kingdoms"),
    ("Lü Bu", "warrior Three Kingdoms"),
    ("Jiang Ziya", "strategist Zhou dynasty"),
    ("Gao Changgong", "Prince of Lanling"),

    # Greek
    ("Minotaur", "Greek mythology"),
    ("Astraea", "Greek goddess justice"),
    ("Caeneus", "Greek mythology"),
    ("Enkidu", "Mesopotamian mythology"),
    ("Ereshkigal", "Mesopotamian goddess underworld"),

    # Indian
    ("Parvati", "Hindu goddess"),
    ("Lakshmibai", "Rani of Jhansi"),
    ("Ashwatthama", "Mahabharata"),
    ("Vritra", "Hindu dragon"),
    ("Kama", "Hindu god love"),

    # European
    ("Chevalier d'Éon", "French spy"),
    ("Blackbeard", "pirate"),
    ("Anne Bonny", "pirate"),
    ("Bradamante", "Orlando Furioso"),
    ("Mandricardo", "Orlando Furioso"),
    ("Professor Moriarty", "Sherlock Holmes"),
    ("Constantine XI", "Byzantine emperor"),
    ("Ptolemy I Soter", "Egyptian king"),
    ("Hephaestion", "Alexander general"),
    ("Solomon ibn Gabirol", "Jewish poet"),
    ("Kriemhild", "Nibelungenlied"),

    # Vietnamese
    ("Trưng Sisters", "Vietnamese"),

    # American
    ("Abigail Williams", "Salem witch trials"),
]


def search_wikidata(query, hint=""):
    """Search Wikidata for the most relevant result"""
    full_query = f"{query} {hint}" if hint else query
    url = 'https://www.wikidata.org/w/api.php'
    params = {
        'action': 'wbsearchentities',
        'search': full_query,
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

    for name, hint in NAMES_TO_SEARCH:
        search_results = search_wikidata(name, hint)

        if search_results:
            best = search_results[0]
            results[name] = {
                "qid": best['id'],
                "label": best.get('label', ''),
                "description": best.get('description', ''),
                "all_results": [
                    {"qid": r['id'], "label": r.get('label', ''), "desc": r.get('description', '')[:100]}
                    for r in search_results[:3]
                ]
            }
            log_lines.append(f"{name}: {best['id']} - {best.get('label', '')} - {best.get('description', '')[:60]}")
        else:
            results[name] = None
            log_lines.append(f"{name}: NOT FOUND")

        time.sleep(0.5)

    # Save results
    output_path = PROJECT_ROOT / "data/raw/atlas_academy/wikidata_qid_search.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Save log
    log_path = PROJECT_ROOT / "poc/data/qid_search_log.txt"
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    print(f"Results saved to: {output_path}")
    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()
