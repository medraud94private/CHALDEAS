"""
Wikipedia 전체 본문 추출 - kiwix_extract_all.py 수정 버전

기존 버전의 문제:
- summary가 5000자 중 첫 문장 300자만 추출
- 전체 본문(content)이 없음

이 버전:
- 전체 본문을 content 필드로 저장
- wikipedia_url 필드 추가
- qid, 날짜 등 기존 정보 유지

Usage:
    python kiwix_extract_full.py --limit 1000      # 테스트
    python kiwix_extract_full.py --resume          # 이어서
    python kiwix_extract_full.py --full            # 전체 (수 시간)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import argparse
from pathlib import Path
from typing import Optional, Tuple
from html.parser import HTMLParser

from libzim.reader import Archive

# ============ Config ============

ZIM_PATH = Path(__file__).parent.parent.parent / "data" / "kiwix" / "wikipedia_en_nopic.zim"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_full"  # 새 폴더
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"

WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki/"

_archive = None

def get_archive() -> Archive:
    global _archive
    if _archive is None:
        _archive = Archive(str(ZIM_PATH))
    return _archive


# ============ HTML Text Extractor (개선) ============

class FullTextExtractor(HTMLParser):
    """HTML에서 전체 텍스트 추출 (개선 버전)"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'sup', 'sub'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1
        # 블록 태그 후 줄바꿈
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self) -> str:
        text = ''.join(self.text_parts)
        # 연속 공백/줄바꿈 정리
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n +', '\n', text)
        return text.strip()


def html_to_full_text(html: str) -> str:
    """HTML을 전체 텍스트로 변환"""
    parser = FullTextExtractor()
    try:
        parser.feed(html)
    except:
        pass
    return parser.get_text()


def html_to_summary(html: str) -> str:
    """첫 문단 추출 (기존 호환)"""
    text = html_to_full_text(html[:10000])
    paragraphs = text.split('\n\n')
    for p in paragraphs:
        p = p.strip()
        if len(p) > 50:  # 의미있는 첫 문단
            return p[:500]
    return text[:500] if text else ""


# ============ Entity Classification (기존 유지) ============

def classify_entity(html: str, title: str) -> Optional[str]:
    """엔티티 유형 분류: person, location, event, None"""
    html_lower = html[:80000].lower()
    first_5000 = html_lower[:5000]
    title_lower = title.lower()

    # ===== PERSON =====
    if 'personal details' in html_lower and '>born<' in html_lower:
        return 'person'

    person_infoboxes = ['infobox biography', 'infobox person', 'infobox military person',
                        'infobox philosopher', 'infobox scientist', 'infobox writer',
                        'infobox politician', 'infobox monarch', 'infobox officeholder']
    for pattern in person_infoboxes:
        if pattern in html_lower:
            return 'person'

    if re.search(r'\(\d{4}\s*[–\-–]\s*\d{4}\)', first_5000):
        if ' was a ' in first_5000 or ' was an ' in first_5000:
            return 'person'

    occupations = ['politician', 'emperor', 'king', 'queen', 'general', 'philosopher',
                   'scientist', 'writer', 'poet', 'composer', 'president', 'pope']
    for occ in occupations:
        if f'was a {occ}' in first_5000 or f'was an {occ}' in first_5000:
            return 'person'

    # ===== EVENT =====
    event_infoboxes = [
        'infobox military conflict', 'infobox battle', 'infobox civil conflict',
        'infobox civilian attack', 'infobox terrorist attack',
        'infobox earthquake', 'infobox eruption', 'infobox volcanic eruption',
        'infobox tropical cyclone', 'infobox hurricane', 'infobox typhoon',
        'infobox storm', 'infobox flood', 'infobox wildfire', 'infobox tornado',
        'infobox tsunami', 'infobox avalanche', 'infobox landslide',
        'infobox election', 'infobox referendum', 'infobox treaty',
        'infobox legislation', 'infobox constitution', 'infobox coronation',
        'infobox coup', 'infobox protest', 'infobox riot',
        'infobox aircraft accident', 'infobox aviation accident',
        'infobox ship accident', 'infobox rail accident', 'infobox shipwreck',
        'infobox disaster', 'infobox famine', 'infobox pandemic', 'infobox epidemic',
        'infobox spaceflight', 'infobox space mission', 'infobox expedition',
        'infobox voyage', 'infobox discovery',
        'infobox event', 'infobox recurring event', 'infobox festival',
        'infobox academic conference', 'infobox summit', 'infobox convention',
        'infobox historical event', 'infobox ceremony',
    ]
    for pattern in event_infoboxes:
        if pattern in html_lower:
            return 'event'

    if 'belligerents' in html_lower and 'casualties' in html_lower:
        return 'event'

    event_title_patterns = [
        'battle of', 'war of', 'siege of', 'massacre of', 'conquest of',
        'invasion of', 'bombing of', 'raid on', 'attack on',
        'revolution', 'rebellion', 'uprising', 'coup d', 'mutiny',
        'assassination of', 'execution of', 'coronation of', 'abdication of',
        'treaty of', 'congress of', 'conference of', 'convention of',
        'accord', 'armistice', 'peace of', 'pact of',
        'earthquake', 'eruption', 'tsunami', 'hurricane', 'typhoon',
        'cyclone', 'flood', 'famine', 'plague', 'pandemic',
        'disaster', 'explosion', 'fire of', 'collapse of', 'sinking of',
        'expedition', 'voyage of', 'discovery of', 'exploration of',
        'construction of', 'founding of', 'destruction of', 'fall of',
    ]
    for pattern in event_title_patterns:
        if pattern in title_lower:
            return 'event'

    # ===== LOCATION =====
    if 'coordinates' in html_lower and 'population' in html_lower:
        return 'location'

    if re.search(r'\d+°\d+', html_lower[:10000]):
        geo_keywords = ['country', 'city', 'capital', 'province', 'region', 'island']
        for kw in geo_keywords:
            if kw in first_5000:
                return 'location'

    if 'infobox settlement' in html_lower or 'infobox country' in html_lower:
        return 'location'

    return None


# ============ Data Extraction ============

def extract_wikidata_qid(html: str) -> Optional[str]:
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    return match.group(1) if match else None


def extract_internal_links(html: str) -> list[str]:
    """Wikipedia 내부 링크 추출 (다른 문서로의 링크)

    나중에 엔티티 간 관계 생성에 사용
    예: Albert Einstein 문서 → [Germany, Max Planck, World War II, ...]
    """
    links = set()

    # href="/wiki/XXX" 또는 href="./XXX" 패턴
    patterns = [
        r'href="/wiki/([^"#:]+)"',      # /wiki/Article_Name
        r'href="\./([^"#:]+)"',          # ./Article_Name (ZIM 내부)
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, html):
            link = match.group(1)
            # 특수 페이지 제외
            if not link.startswith(('File:', 'Category:', 'Template:', 'Help:',
                                     'Wikipedia:', 'Portal:', 'Special:', 'Talk:',
                                     'User:', 'Module:', 'MediaWiki:')):
                # URL 디코딩
                link = link.replace('_', ' ')
                links.add(link)

    return list(links)


def extract_years(html: str) -> Tuple[Optional[int], Optional[int]]:
    """년도 추출"""
    text = html_to_full_text(html[:5000])

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
    patterns = [
        r'(\d+)°(\d+)′?[NS].*?(\d+)°(\d+)′?[EW]',
        r'latitude["\s:]+(\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, html[:20000])
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(3)) if len(match.groups()) > 2 else None
                return lat, lon
            except:
                continue

    return None, None


# ============ Main Processing ============

CHECKPOINT_INTERVAL = 500


def count_file_lines(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    with open(filepath, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)


def sync_stats_with_files() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return {
        'persons': count_file_lines(OUTPUT_DIR / "persons.jsonl"),
        'locations': count_file_lines(OUTPUT_DIR / "locations.jsonl"),
        'events': count_file_lines(OUTPUT_DIR / "events.jsonl"),
    }


def load_existing_paths() -> set:
    """이미 처리된 path들을 set으로 로드"""
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
    """Wikipedia에서 전체 본문 포함 추출"""
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

    print("Loading existing paths for dedup...", flush=True)
    existing_paths = load_existing_paths()
    print(f"Loaded {len(existing_paths):,} existing paths", flush=True)

    print(f"Wikipedia ZIM: {total_entries:,} entries", flush=True)
    print(f"Starting from: {start_index:,}", flush=True)
    print(f"Limit: {limit:,}", flush=True)
    print(f"Output: {OUTPUT_DIR}", flush=True)
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

            # ★ 핵심 변경: 전체 본문 추출
            full_content = html_to_full_text(html)
            summary = html_to_summary(html)
            wikipedia_url = WIKIPEDIA_BASE_URL + path

            # ★ 내부 링크 추출 (관계 생성용)
            internal_links = extract_internal_links(html)

            if entity_type == 'person':
                birth, death = extract_years(html)
                # 역사적 인물만 (사망 또는 1925년 이전 출생)
                if not death and (not birth or birth > 1925):
                    continue

                data = {
                    'title': entry.title,
                    'qid': qid,
                    'path': path,
                    'wikipedia_url': wikipedia_url,
                    'birth_year': birth,
                    'death_year': death,
                    'summary': summary,
                    'content': full_content,  # ★ 전체 본문
                    'links': internal_links,  # ★ 내부 링크
                }
                append_entity('person', data)
                stats['persons'] += 1

            elif entity_type == 'location':
                lat, lon = extract_coordinates(html)
                data = {
                    'title': entry.title,
                    'qid': qid,
                    'path': path,
                    'wikipedia_url': wikipedia_url,
                    'latitude': lat,
                    'longitude': lon,
                    'summary': summary,
                    'content': full_content,  # ★ 전체 본문
                    'links': internal_links,  # ★ 내부 링크
                }
                append_entity('location', data)
                stats['locations'] += 1

            elif entity_type == 'event':
                start_year, end_year = extract_years(html)
                data = {
                    'title': entry.title,
                    'qid': qid,
                    'path': path,
                    'wikipedia_url': wikipedia_url,
                    'start_year': start_year,
                    'end_year': end_year,
                    'summary': summary,
                    'content': full_content,  # ★ 전체 본문
                    'links': internal_links,  # ★ 내부 링크
                }
                append_entity('event', data)
                stats['events'] += 1

            # 진행 상황
            total_found = stats['persons'] + stats['locations'] + stats['events']
            if total_found % 200 == 0 and total_found > 0:
                pct = i / total_entries * 100
                dup = stats.get('skipped_duplicate', 0)
                print(f"[{i:,}/{total_entries:,} ({pct:.1f}%)] P:{stats['persons']:,} L:{stats['locations']:,} E:{stats['events']:,}", flush=True)

        except Exception as e:
            pass

        finally:
            if (i - start_index + 1) % CHECKPOINT_INTERVAL == 0:
                pct = (i + 1) / total_entries * 100
                save_checkpoint(i + 1, stats)
                print(f"  [Checkpoint {i+1:,}] P:{stats['persons']:,} L:{stats['locations']:,} E:{stats['events']:,}", flush=True)

    save_checkpoint(end_index, stats)

    print("-" * 60, flush=True)
    print("Completed!", flush=True)
    print(json.dumps(stats, indent=2), flush=True)


def show_stats():
    _, stats = load_checkpoint()
    print("Current stats:")
    print(json.dumps(stats, indent=2))

    total_size = 0
    for entity_type in ['persons', 'locations', 'events']:
        filepath = OUTPUT_DIR / f"{entity_type}.jsonl"
        if filepath.exists():
            count = count_file_lines(filepath)
            size_mb = filepath.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"{entity_type}: {count:,} records, {size_mb:.1f} MB")

    print(f"\nTotal size: {total_size:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description="Extract full content from Wikipedia")
    parser.add_argument("--limit", type=int, default=1000)
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
