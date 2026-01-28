"""
Wikipedia 재스캔 - 미분류 문서에서 EVENT 추가 추출

이전 추출에서 unclassified로 남은 6.9M 문서를 확장된 분류 로직으로 재스캔

Usage:
    python kiwix_rescan_events.py --limit 100000
    python kiwix_rescan_events.py --resume
    python kiwix_rescan_events.py --full
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import argparse
from pathlib import Path
from typing import Optional, Set
from html.parser import HTMLParser

from libzim.reader import Archive

# ============ Config ============

ZIM_PATH = Path(__file__).parent.parent.parent / "data" / "kiwix" / "wikipedia_en_nopic.zim"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_extract"
CHECKPOINT_FILE = OUTPUT_DIR / "rescan_checkpoint.json"
EVENTS_FILE = OUTPUT_DIR / "events.jsonl"

_archive = None

def get_archive() -> Archive:
    global _archive
    if _archive is None:
        _archive = Archive(str(ZIM_PATH))
    return _archive


# ============ Simple Text Extractor ============

class SimpleTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav') and self.skip > 0:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip == 0:
            self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)


def html_to_text(html: str) -> str:
    parser = SimpleTextExtractor()
    try:
        parser.feed(html)
    except:
        pass
    return parser.get_text()


# ============ EVENT Classification (확장) ============

def is_event(html: str, title: str) -> bool:
    """EVENT 여부만 판단 (확장된 로직)"""
    html_lower = html[:80000].lower()
    first_5000 = html_lower[:5000]
    title_lower = title.lower()

    # Person 체크 (제외)
    if 'personal details' in html_lower and '>born<' in html_lower:
        return False
    person_infoboxes = ['infobox biography', 'infobox person', 'infobox military person',
                        'infobox philosopher', 'infobox scientist', 'infobox writer',
                        'infobox politician', 'infobox monarch', 'infobox officeholder']
    for pattern in person_infoboxes:
        if pattern in html_lower:
            return False
    if re.search(r'\(\d{4}\s*[–\-–]\s*\d{4}\)', first_5000):
        if ' was a ' in first_5000 or ' was an ' in first_5000:
            return False

    # Location 체크 (제외)
    if 'coordinates' in html_lower and 'population' in html_lower:
        return False
    if 'infobox settlement' in html_lower or 'infobox country' in html_lower:
        return False

    # ===== EVENT 판단 =====

    # 1. Infobox 기반 분류 (가장 신뢰도 높음)
    event_infoboxes = [
        # 군사/충돌
        'infobox military conflict', 'infobox battle', 'infobox civil conflict',
        'infobox civilian attack', 'infobox terrorist attack',
        # 자연재해
        'infobox earthquake', 'infobox eruption', 'infobox volcanic eruption',
        'infobox tropical cyclone', 'infobox hurricane', 'infobox typhoon',
        'infobox storm', 'infobox flood', 'infobox wildfire', 'infobox tornado',
        'infobox tsunami', 'infobox avalanche', 'infobox landslide',
        # 정치/법률
        'infobox election', 'infobox referendum', 'infobox treaty',
        'infobox legislation', 'infobox constitution', 'infobox coronation',
        'infobox coup', 'infobox protest', 'infobox riot',
        # 사고/재난
        'infobox aircraft accident', 'infobox aviation accident',
        'infobox ship accident', 'infobox rail accident', 'infobox shipwreck',
        'infobox disaster', 'infobox famine', 'infobox pandemic', 'infobox epidemic',
        # 탐험/과학
        'infobox spaceflight', 'infobox space mission', 'infobox expedition',
        'infobox voyage', 'infobox discovery',
        # 일반 이벤트
        'infobox event', 'infobox recurring event', 'infobox festival',
        'infobox academic conference', 'infobox summit', 'infobox convention',
        'infobox historical event', 'infobox ceremony',
    ]
    for pattern in event_infoboxes:
        if pattern in html_lower:
            return True

    # 2. 전투/전쟁 특징 (belligerents + casualties)
    if 'belligerents' in html_lower and 'casualties' in html_lower:
        return True

    # 3. 타이틀 기반 분류
    event_title_patterns = [
        # 군사
        'battle of', 'war of', 'siege of', 'massacre of', 'conquest of',
        'invasion of', 'bombing of', 'raid on', 'attack on',
        # 정치
        'revolution', 'rebellion', 'uprising', 'coup d', 'mutiny',
        'assassination of', 'execution of', 'coronation of', 'abdication of',
        # 조약/협정
        'treaty of', 'congress of', 'conference of', 'convention of',
        'accord', 'armistice', 'peace of', 'pact of',
        # 자연재해
        'earthquake', 'eruption', 'tsunami', 'hurricane', 'typhoon',
        'cyclone', 'flood', 'famine', 'plague', 'pandemic',
        # 사고
        'disaster', 'explosion', 'fire of', 'collapse of', 'sinking of',
        # 탐험/발견
        'expedition', 'voyage of', 'discovery of', 'exploration of',
        # 건설/파괴
        'construction of', 'founding of', 'destruction of', 'fall of',
    ]
    for pattern in event_title_patterns:
        if pattern in title_lower:
            return True

    # 4. 연도 + 이벤트 키워드 제목 (예: "1906 San Francisco earthquake")
    # 단순 연도 시작은 너무 broad (109 BC, 109 Felicitas 등 제외)
    year_event_patterns = [
        r'^\d{4}\s+.*earthquake',
        r'^\d{4}\s+.*eruption',
        r'^\d{4}\s+.*tsunami',
        r'^\d{4}\s+.*hurricane',
        r'^\d{4}\s+.*typhoon',
        r'^\d{4}\s+.*flood',
        r'^\d{4}\s+.*fire\b',
        r'^\d{4}\s+.*massacre',
        r'^\d{4}\s+.*riots?',
        r'^\d{4}\s+.*election',
        r'^\d{4}\s+.*coup',
        r'^\d{4}\s+.*revolution',
        r'^\d{4}\s+.*war\b',
        r'^\d{4}\s+.*invasion',
        r'^\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',  # "10 May 2010 ..."
    ]
    for pattern in year_event_patterns:
        if re.match(pattern, title_lower):
            return True

    # 5. 내용 기반 분류 (날짜 + 이벤트 동사)
    event_verbs = [
        'took place', 'occurred', 'happened', 'began', 'ended',
        'was fought', 'was signed', 'was held', 'was established',
        'erupted', 'struck', 'hit', 'devastated', 'destroyed',
    ]
    # 특정 날짜 패턴 (on January 1, 1900 / in 1900)
    has_date = bool(re.search(r'(on|in)\s+(january|february|march|april|may|june|july|august|september|october|november|december)?\s*\d{1,2}?,?\s*\d{3,4}', first_5000, re.IGNORECASE))
    if has_date:
        for verb in event_verbs:
            if verb in first_5000:
                # person이 아닌 경우만
                if ' was a ' not in first_5000 and ' was an ' not in first_5000:
                    return True

    # 6. 결과/피해 정보가 있는 경우
    if ('casualties' in html_lower or 'deaths' in html_lower[:10000]) and 'result' in html_lower[:10000]:
        if 'belligerents' in html_lower or 'combatants' in html_lower:
            return True
        # 재해 관련 키워드
        if any(kw in html_lower[:10000] for kw in ['magnitude', 'epicenter', 'damage', 'destroyed', 'injured']):
            return True

    return False


# ============ Data Extraction ============

def extract_wikidata_qid(html: str) -> Optional[str]:
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    return match.group(1) if match else None


def extract_years(html: str) -> tuple:
    """년도 추출"""
    text = html_to_text(html[:5000])
    patterns = [
        r'\((\d{4})\s*[–\-–]\s*(\d{4})\)',
        r'(\d{4})\s*[–\-–]\s*(\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1)), int(match.group(2))
            except:
                continue
    return None, None


def extract_summary(html: str) -> str:
    """첫 문장 추출"""
    text = html_to_text(html[:5000])
    sentences = text.split('.')
    if sentences:
        return sentences[0].strip()[:300]
    return ""


# ============ Main Processing ============

CHECKPOINT_INTERVAL = 1000


def load_existing_paths() -> Set[str]:
    """이미 분류된 모든 path 로드"""
    existing = set()
    for entity_type in ['persons', 'locations', 'events']:
        filepath = OUTPUT_DIR / f"{entity_type}.jsonl"
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if 'path' in data:
                            existing.add(data['path'])
                    except:
                        pass
    return existing


def load_checkpoint() -> tuple:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('last_index', 0), data.get('stats', {})
    return 0, {}


def save_checkpoint(index: int, stats: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'last_index': index, 'stats': stats}, f, indent=2)


def append_event(data: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')


def rescan_events(limit: int = 100000, resume: bool = True):
    """미분류 문서에서 EVENT 재추출"""
    zim = get_archive()
    total_entries = zim.entry_count

    start_index, stats = load_checkpoint() if resume else (0, {})

    if not stats:
        stats = {
            'scanned': 0,
            'new_events': 0,
            'skipped_classified': 0,
            'skipped_redirect': 0,
            'skipped_non_article': 0,
            'not_event': 0,
        }

    # 이미 분류된 path 로드
    print("Loading existing classified paths...", flush=True)
    existing_paths = load_existing_paths()
    print(f"Loaded {len(existing_paths):,} classified paths", flush=True)

    print(f"Wikipedia ZIM: {total_entries:,} entries", flush=True)
    print(f"Starting from: {start_index:,}", flush=True)
    print(f"Limit: {limit:,}", flush=True)
    print("-" * 60, flush=True)

    end_index = min(start_index + limit, total_entries)

    for i in range(start_index, end_index):
        try:
            entry = zim._get_entry_by_id(i)
            stats['scanned'] += 1

            if entry.is_redirect:
                stats['skipped_redirect'] += 1
                continue

            path = entry.path
            if path.startswith('_') or path.startswith('-') or '/' in path:
                stats['skipped_non_article'] += 1
                continue

            # 이미 분류된 문서 스킵
            if path in existing_paths:
                stats['skipped_classified'] += 1
                continue

            # HTML 가져오기
            try:
                item = entry.get_item()
                html = bytes(item.content).decode('utf-8', errors='ignore')
            except:
                continue

            # EVENT 판단
            if is_event(html, entry.title):
                qid = extract_wikidata_qid(html)
                start_year, end_year = extract_years(html)
                summary = extract_summary(html)

                data = {
                    'title': entry.title,
                    'qid': qid,
                    'start_year': start_year,
                    'end_year': end_year,
                    'summary': summary,
                    'path': path,
                }
                append_event(data)
                existing_paths.add(path)  # 중복 방지
                stats['new_events'] += 1
            else:
                stats['not_event'] += 1

            # 진행 상황
            if stats['new_events'] > 0 and stats['new_events'] % 500 == 0:
                pct = i / total_entries * 100
                print(f"[{i:,}/{total_entries:,} ({pct:.1f}%)] New events: {stats['new_events']:,}", flush=True)

        except Exception as e:
            pass

        finally:
            # 체크포인트 (1000개마다)
            if (i - start_index + 1) % CHECKPOINT_INTERVAL == 0:
                pct = (i + 1) / total_entries * 100
                save_checkpoint(i + 1, stats)
                print(f"  [{i+1:,}/{total_entries:,} ({pct:.1f}%)] New: {stats['new_events']:,} | Classified: {stats['skipped_classified']:,}", flush=True)

    save_checkpoint(end_index, stats)

    print("-" * 60, flush=True)
    print("Completed!", flush=True)
    print(json.dumps(stats, indent=2), flush=True)


def show_stats():
    _, stats = load_checkpoint()
    print("Rescan stats:")
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Rescan unclassified articles for events")
    parser.add_argument("--limit", type=int, default=100000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--stats", action="store_true")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    limit = 20000000 if args.full else args.limit
    rescan_events(limit=limit, resume=args.resume)


if __name__ == "__main__":
    main()
