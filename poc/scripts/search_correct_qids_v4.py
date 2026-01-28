"""
Final search for remaining names
"""
import requests
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
HEADERS = {"User-Agent": "ChaldeasBot/1.0 (https://chaldeas.site)"}

NAMES_TO_SEARCH = [
    "Saito Hajime",
    "Kintaro",
    "Benkei monk",
    "Kiyohime",
    "Edward Teach pirate",
    "Astraea goddess mythology",
    "Kriemhild Nibelungenlied",
    "Abigail Williams Salem witch",
    "Kamadeva",
    "Professor Moriarty Sherlock",
]


def search_wikidata(query):
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
    except:
        return []


def main():
    log_lines = []

    for name in NAMES_TO_SEARCH:
        search_results = search_wikidata(name)

        if search_results:
            for r in search_results[:3]:
                log_lines.append(f"{name}: {r['id']} | {r.get('label', '')} | {r.get('description', '')[:80]}")
            log_lines.append("")
        else:
            log_lines.append(f"{name}: NOT FOUND")
            log_lines.append("")

        time.sleep(0.3)

    log_path = PROJECT_ROOT / "poc/data/qid_search_log_v4.txt"
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()
