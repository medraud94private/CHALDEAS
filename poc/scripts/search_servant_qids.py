"""
FGO 서번트의 올바른 Wikidata QID 검색
"""
import requests
import json
import time
from pathlib import Path

HEADERS = {'User-Agent': 'ChaldeasBot/1.0 (https://chaldeas.site)'}
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data/raw/atlas_academy/verified_servant_qids.json"

# 서번트 검색 리스트 (이름, 필터 키워드)
SERVANTS_TO_SEARCH = [
    # Saber
    ("King Arthur", "legendary british"),
    ("Nero", "roman emperor"),
    ("Julius Caesar", "roman"),
    ("Siegfried", "nibelungen"),
    ("Gawain", "arthurian"),
    ("Lancelot", "arthurian"),
    ("Mordred", "arthurian"),
    ("Bedivere", "arthurian"),
    ("Miyamoto Musashi", "swordsman"),
    ("Okita Soji", "shinsengumi"),

    # Archer
    ("Gilgamesh", "sumerian"),
    ("Robin Hood", "folk hero"),
    ("Atalanta", "greek mythology"),
    ("Arjuna", "mahabharata"),
    ("Nikola Tesla", "inventor"),
    ("Napoleon Bonaparte", "french emperor"),
    ("Paris", "trojan prince"),
    ("Chiron", "centaur"),

    # Lancer
    ("Cu Chulainn", "irish mythology"),
    ("Leonidas I", "spartan king"),
    ("Romulus", "founder of rome"),
    ("Hector", "trojan"),
    ("Scathach", "irish mythology"),
    ("Karna", "mahabharata"),
    ("Brynhildr", "norse"),
    ("Vlad III", "wallachia"),
    ("Enkidu", "mesopotam"),

    # Rider
    ("Alexander the Great", "macedon"),
    ("Medusa", "greek mythology gorgon"),
    ("Boudica", "celtic queen"),
    ("Francis Drake", "english"),
    ("Achilles", "greek hero"),
    ("Minamoto no Yoshitsune", "samurai"),
    ("Ivan the Terrible", "tsar"),
    ("Christopher Columbus", "explorer"),
    ("Marie Antoinette", "queen france"),
    ("Ramesses II", "pharaoh"),
    ("Quetzalcoatl", "aztec"),

    # Caster
    ("Medea", "greek sorceress"),
    ("Hans Christian Andersen", "author"),
    ("William Shakespeare", "playwright"),
    ("Solomon", "king israel"),
    ("Merlin", "wizard"),
    ("Leonardo da Vinci", "artist"),
    ("Xuanzang", "buddhist monk"),
    ("Paracelsus", "alchemist"),
    ("Thomas Edison", "inventor"),
    ("Helena Blavatsky", "theosoph"),
    ("Circe", "greek sorceress"),

    # Assassin
    ("Sasaki Kojiro", "swordsman"),
    ("Mata Hari", "spy"),
    ("Jack the Ripper", "serial killer"),
    ("Elizabeth Bathory", "countess"),
    ("Cleopatra", "egyptian queen"),
    ("Semiramis", "assyria"),
    ("Wu Zetian", "empress china"),
    ("Charlotte Corday", "french revolution"),

    # Berserker
    ("Heracles", "greek hero zeus"),
    ("Spartacus", "gladiator"),
    ("Caligula", "roman emperor"),
    ("Darius III", "persian"),
    ("Frankenstein monster", "novel"),
    ("Beowulf", "epic poem"),
    ("Florence Nightingale", "nurse"),
    ("Penthesilea", "amazon queen"),
    ("Paul Bunyan", "folk tale"),

    # Ruler
    ("Joan of Arc", "french saint"),
    ("Amakusa Shiro", "shimabara"),
    ("Sherlock Holmes", "detective"),
    ("Qin Shi Huang", "chinese emperor"),
    ("Himiko", "japanese queen"),

    # Others
    ("Edmond Dantes", "count monte cristo"),
    ("Antonio Salieri", "composer"),
    ("Abigail Williams", "salem"),
    ("Katsushika Hokusai", "artist"),
    ("Yang Guifei", "chinese consort"),
    ("Vincent van Gogh", "painter"),
]


def search_wikidata(query, filter_text=None):
    """Search Wikidata for entity"""
    url = 'https://www.wikidata.org/w/api.php'
    params = {
        'action': 'wbsearchentities',
        'search': query,
        'language': 'en',
        'format': 'json',
        'limit': 10
    }

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        results = r.json().get('search', [])

        for result in results:
            desc = result.get('description', '').lower()
            if filter_text:
                # Check if any filter word matches
                filter_words = filter_text.lower().split()
                if any(word in desc for word in filter_words):
                    return {
                        'qid': result['id'],
                        'label': result['label'],
                        'description': result.get('description', '')
                    }
            else:
                return {
                    'qid': result['id'],
                    'label': result['label'],
                    'description': result.get('description', '')
                }
        return None
    except Exception as e:
        print(f"Error searching {query}: {e}")
        return None


def main():
    verified = {}
    failed = []

    for name, filter_text in SERVANTS_TO_SEARCH:
        result = search_wikidata(name, filter_text)

        if result:
            verified[name] = result
            try:
                print(f"[OK] {name}: {result['qid']}")
            except:
                print(f"[OK] {name}: {result['qid']} (encoding issue)")
        else:
            failed.append(name)
            print(f"[FAIL] {name}")

        time.sleep(0.3)

    # Save results
    output = {
        'verified': verified,
        'failed': failed,
        'stats': {
            'total': len(SERVANTS_TO_SEARCH),
            'verified': len(verified),
            'failed': len(failed)
        }
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== Summary ===")
    print(f"Verified: {len(verified)}/{len(SERVANTS_TO_SEARCH)}")
    print(f"Failed: {failed}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
