"""
Wikipedia 통합 추출 - 인물/장소/사건 동시 분류

한 번 스캔으로 세 가지 유형 모두 추출

Usage:
    python kiwix_extract_all.py --limit 100000
    python kiwix_extract_all.py --resume
    python kiwix_extract_all.py --full
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import argparse
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass, asdict
from html.parser import HTMLParser

from libzim.reader import Archive

# ============ Config ============

ZIM_PATH = Path(__file__).parent.parent.parent / "data" / "kiwix" / "wikipedia_en_nopic.zim"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_extract"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"

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


# ============ Entity Classification ============

def classify_entity(html: str, title: str) -> Optional[str]:
    """엔티티 유형 분류: person, location, event, None"""
    html_lower = html[:80000].lower()
    first_5000 = html_lower[:5000]
    title_lower = title.lower()

    # ===== PERSON =====
    # Personal details + Born
    if 'personal details' in html_lower and '>born<' in html_lower:
        return 'person'

    # Infobox person 류
    person_infoboxes = ['infobox biography', 'infobox person', 'infobox military person',
                        'infobox philosopher', 'infobox scientist', 'infobox writer',
                        'infobox politician', 'infobox monarch', 'infobox officeholder']
    for pattern in person_infoboxes:
        if pattern in html_lower:
            return 'person'

    # (년도–년도) + was a/an
    if re.search(r'\(\d{4}\s*[–\-–]\s*\d{4}\)', first_5000):
        if ' was a ' in first_5000 or ' was an ' in first_5000:
            return 'person'

    # 직업 키워드
    occupations = ['politician', 'emperor', 'king', 'queen', 'general', 'philosopher',
                   'scientist', 'writer', 'poet', 'composer', 'president', 'pope']
    for occ in occupations:
        if f'was a {occ}' in first_5000 or f'was an {occ}' in first_5000:
            return 'person'

    # ===== EVENT (확장) =====

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
            return 'event'

    # 2. 전투/전쟁 특징 (belligerents + casualties)
    if 'belligerents' in html_lower and 'casualties' in html_lower:
        return 'event'

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
            return 'event'

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
            return 'event'

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
                    return 'event'

    # 6. 결과/피해 정보가 있는 경우
    if ('casualties' in html_lower or 'deaths' in html_lower[:10000]) and 'result' in html_lower[:10000]:
        if 'belligerents' in html_lower or 'combatants' in html_lower:
            return 'event'
        # 재해 관련 키워드
        if any(kw in html_lower[:10000] for kw in ['magnitude', 'epicenter', 'damage', 'destroyed', 'injured']):
            return 'event'

    # ===== LOCATION =====
    # 좌표 + 인구
    if 'coordinates' in html_lower and 'population' in html_lower:
        return 'location'

    # lat/lon 패턴 + 지리 키워드
    if re.search(r'\d+°\d+', html_lower[:10000]):
        geo_keywords = ['country', 'city', 'capital', 'province', 'region', 'island']
        for kw in geo_keywords:
            if kw in first_5000:
                return 'location'

    # Infobox settlement/country
    if 'infobox settlement' in html_lower or 'infobox country' in html_lower:
        return 'location'

    return None


# ============ Data Extraction ============

def extract_wikidata_qid(html: str) -> Optional[str]:
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    return match.group(1) if match else None


def extract_years(html: str) -> Tuple[Optional[int], Optional[int]]:
    """년도 추출 (인물: 생몰년, 사건: 시작/종료)"""
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


def extract_coordinates(html: str) -> Tuple[Optional[float], Optional[float]]:
    """좌표 추출"""
    # 다양한 좌표 패턴
    patterns = [
        r'(\d+)°(\d+)′?[NS].*?(\d+)°(\d+)′?[EW]',
        r'latitude["\s:]+(\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, html[:20000])
        if match:
            try:
                # 간단히 도 단위만
                lat = float(match.group(1))
                lon = float(match.group(3)) if len(match.groups()) > 2 else None
                return lat, lon
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

CHECKPOINT_INTERVAL = 1000  # 체크포인트 저장 빈도


def count_file_lines(filepath: Path) -> int:
    """파일 라인 수 계산"""
    if not filepath.exists():
        return 0
    with open(filepath, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)


def sync_stats_with_files() -> dict:
    """파일에서 실제 엔티티 수를 읽어서 통계 동기화"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return {
        'persons': count_file_lines(OUTPUT_DIR / "persons.jsonl"),
        'locations': count_file_lines(OUTPUT_DIR / "locations.jsonl"),
        'events': count_file_lines(OUTPUT_DIR / "events.jsonl"),
    }


def load_existing_paths() -> set:
    """이미 처리된 path들을 set으로 로드 (중복 방지용)

    Note: 현재 ~200k paths = ~50MB 메모리 사용
    전체 추출 시 ~1M paths = ~200MB 예상 (허용 범위)
    """
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


def load_checkpoint() -> Tuple[int, dict]:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            stats = data.get('stats', {})
            # 파일과 통계 동기화 (재시작 시 중복 방지)
            file_counts = sync_stats_with_files()
            stats['persons'] = file_counts['persons']
            stats['locations'] = file_counts['locations']
            stats['events'] = file_counts['events']
            return data.get('last_index', 0), stats
    return 0, {}


def save_checkpoint(index: int, stats: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'last_index': index, 'stats': stats}, f, indent=2)


def append_entity(entity_type: str, data: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / f"{entity_type}s.jsonl"
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')


def extract_all(limit: int = 100000, resume: bool = True):
    """Wikipedia에서 인물/장소/사건 동시 추출"""
    zim = get_archive()
    total_entries = zim.entry_count

    start_index, stats = load_checkpoint() if resume else (0, {})

    if not stats:
        stats = {
            'scanned': 0,
            'persons': 0,
            'locations': 0,
            'events': 0,
            'skipped_redirect': 0,
            'skipped_non_article': 0,
            'unclassified': 0,
            'skipped_duplicate': 0,
        }
    if 'skipped_duplicate' not in stats:
        stats['skipped_duplicate'] = 0

    # 이미 처리된 path 로드 (중복 방지)
    print("Loading existing paths for dedup...", flush=True)
    existing_paths = load_existing_paths()
    print(f"Loaded {len(existing_paths):,} existing paths", flush=True)

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

            # 중복 체크
            if path in existing_paths:
                stats['skipped_duplicate'] += 1
                continue

            # HTML 가져오기
            try:
                item = entry.get_item()
                html = bytes(item.content).decode('utf-8', errors='ignore')
            except:
                continue

            # 분류
            entity_type = classify_entity(html, entry.title)

            if not entity_type:
                stats['unclassified'] += 1
                continue

            # 공통 데이터
            qid = extract_wikidata_qid(html)
            summary = extract_summary(html)

            if entity_type == 'person':
                birth, death = extract_years(html)
                # 역사적 인물만 (사망 또는 1925년 이전 출생)
                if not death and (not birth or birth > 1925):
                    continue

                data = {
                    'title': entry.title,
                    'qid': qid,
                    'birth_year': birth,
                    'death_year': death,
                    'summary': summary,
                    'path': path,
                }
                append_entity('person', data)
                stats['persons'] += 1

            elif entity_type == 'location':
                lat, lon = extract_coordinates(html)
                data = {
                    'title': entry.title,
                    'qid': qid,
                    'latitude': lat,
                    'longitude': lon,
                    'summary': summary,
                    'path': path,
                }
                append_entity('location', data)
                stats['locations'] += 1

            elif entity_type == 'event':
                start_year, end_year = extract_years(html)
                data = {
                    'title': entry.title,
                    'qid': qid,
                    'start_year': start_year,
                    'end_year': end_year,
                    'summary': summary,
                    'path': path,
                }
                append_entity('event', data)
                stats['events'] += 1

            # 진행 상황
            total_found = stats['persons'] + stats['locations'] + stats['events']
            if total_found % 500 == 0 and total_found > 0:
                pct = i / total_entries * 100
                dup = stats.get('skipped_duplicate', 0)
                print(f"[{i:,}/{total_entries:,} ({pct:.1f}%)] P:{stats['persons']:,} L:{stats['locations']:,} E:{stats['events']:,} D:{dup:,}", flush=True)

        except Exception as e:
            pass  # 에러 무시하고 계속

        finally:
            # 체크포인트 (1000개마다) - finally에서 항상 실행
            if (i - start_index + 1) % CHECKPOINT_INTERVAL == 0:
                pct = (i + 1) / total_entries * 100
                save_checkpoint(i + 1, stats)
                dup = stats.get('skipped_duplicate', 0)
                print(f"  [{i+1:,}/{total_entries:,} ({pct:.1f}%)] P:{stats['persons']:,} L:{stats['locations']:,} E:{stats['events']:,} D:{dup:,}", flush=True)

    save_checkpoint(end_index, stats)

    print("-" * 60, flush=True)
    print("Completed!", flush=True)
    print(json.dumps(stats, indent=2), flush=True)


def show_stats():
    _, stats = load_checkpoint()
    print("Current stats:")
    print(json.dumps(stats, indent=2))

    for entity_type in ['person', 'location', 'event']:
        filepath = OUTPUT_DIR / f"{entity_type}s.jsonl"
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                count = sum(1 for _ in f)
            print(f"{entity_type}s: {count:,}")


def main():
    parser = argparse.ArgumentParser(description="Extract all entity types from Wikipedia")
    parser.add_argument("--limit", type=int, default=100000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--stats", action="store_true")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    limit = 20000000 if args.full else args.limit
    extract_all(limit=limit, resume=args.resume)


if __name__ == "__main__":
    main()
