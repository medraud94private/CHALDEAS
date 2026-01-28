"""
Wikipedia 전체 본문 추출 - 병렬 처리 버전

16코어 병렬 처리로 ~50시간 → ~4시간으로 단축

출력 필드:
- title, qid, path, wikipedia_url
- summary (첫 문단)
- content (전체 본문, HTML 제거)
- links (내부 링크 리스트 - 문서 연결용)
- 날짜/좌표 등

Usage:
    python kiwix_extract_parallel.py --workers 12 --limit 100000
    python kiwix_extract_parallel.py --workers 12 --full
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import argparse
import multiprocessing as mp
from pathlib import Path
from typing import Optional, Tuple
from html.parser import HTMLParser
from datetime import datetime

from libzim.reader import Archive

# ============ Config ============

ZIM_PATH = Path(__file__).parent.parent.parent / "data" / "kiwix" / "wikipedia_en_nopic.zim"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_full"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint_parallel.json"

WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki/"


# ============ HTML Text Extractor ============

class FullTextExtractor(HTMLParser):
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
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self) -> str:
        text = ''.join(self.text_parts)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n +', '\n', text)
        return text.strip()


def html_to_full_text(html: str) -> str:
    parser = FullTextExtractor()
    try:
        parser.feed(html)
    except:
        pass
    return parser.get_text()


def html_to_summary(html: str) -> str:
    text = html_to_full_text(html[:10000])
    paragraphs = text.split('\n\n')
    for p in paragraphs:
        p = p.strip()
        if len(p) > 50:
            return p[:500]
    return text[:500] if text else ""


# ============ Entity Classification ============

def classify_entity(html: str, title: str) -> Optional[str]:
    html_lower = html[:80000].lower()
    first_5000 = html_lower[:5000]
    title_lower = title.lower()

    # PERSON
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

    # EVENT
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

    # LOCATION
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


def extract_internal_links(html: str) -> list:
    """내부 링크 추출 - 문서 연결용"""
    links = set()
    patterns = [
        r'href="/wiki/([^"#:]+)"',
        r'href="\./([^"#:]+)"',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            link = match.group(1)
            if not link.startswith(('File:', 'Category:', 'Template:', 'Help:',
                                     'Wikipedia:', 'Portal:', 'Special:', 'Talk:',
                                     'User:', 'Module:', 'MediaWiki:')):
                link = link.replace('_', ' ')
                links.add(link)
    return list(links)


def extract_years(html: str) -> Tuple[Optional[int], Optional[int]]:
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


# ============ Worker Function ============

def process_entry(entry_id):
    """단일 엔트리 처리 (워커 함수)"""
    try:
        zim = Archive(str(ZIM_PATH))
        entry = zim._get_entry_by_id(entry_id)

        if entry.is_redirect:
            return None, 'redirect'

        path = entry.path
        if path.startswith('_') or path.startswith('-') or '/' in path:
            return None, 'non_article'

        try:
            item = entry.get_item()
            html = bytes(item.content).decode('utf-8', errors='ignore')
        except:
            return None, 'error'

        entity_type = classify_entity(html, entry.title)
        if not entity_type:
            return None, 'unclassified'

        # 데이터 추출
        qid = extract_wikidata_qid(html)
        full_content = html_to_full_text(html)
        summary = html_to_summary(html)
        wikipedia_url = WIKIPEDIA_BASE_URL + path
        internal_links = extract_internal_links(html)

        if entity_type == 'person':
            birth, death = extract_years(html)
            if not death and (not birth or birth > 1925):
                return None, 'filtered'

            data = {
                'title': entry.title,
                'qid': qid,
                'path': path,
                'wikipedia_url': wikipedia_url,
                'birth_year': birth,
                'death_year': death,
                'summary': summary,
                'content': full_content,
                'links': internal_links,
            }
            return ('person', data), 'ok'

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
                'content': full_content,
                'links': internal_links,
            }
            return ('location', data), 'ok'

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
                'content': full_content,
                'links': internal_links,
            }
            return ('event', data), 'ok'

    except Exception as e:
        return None, 'error'

    return None, 'unknown'


# ============ Main ============

def extract_parallel(num_workers: int = 12, limit: int = None, resume: bool = True):
    """병렬 추출"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ZIM 정보
    zim = Archive(str(ZIM_PATH))
    total_entries = zim.entry_count
    del zim

    # 체크포인트
    start_index = 0
    if resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r') as f:
            data = json.load(f)
            start_index = data.get('last_index', 0)

    end_index = total_entries if limit is None else min(start_index + limit, total_entries)

    print(f"Wikipedia ZIM: {total_entries:,} entries", flush=True)
    print(f"Range: {start_index:,} - {end_index:,}", flush=True)
    print(f"Workers: {num_workers}", flush=True)
    print("-" * 60, flush=True)

    # 파일 핸들
    files = {
        'person': open(OUTPUT_DIR / "persons.jsonl", 'a', encoding='utf-8'),
        'location': open(OUTPUT_DIR / "locations.jsonl", 'a', encoding='utf-8'),
        'event': open(OUTPUT_DIR / "events.jsonl", 'a', encoding='utf-8'),
    }

    stats = {'persons': 0, 'locations': 0, 'events': 0,
             'redirect': 0, 'non_article': 0, 'unclassified': 0, 'error': 0, 'filtered': 0}

    start_time = datetime.now()

    try:
        tasks = list(range(start_index, end_index))

        with mp.Pool(num_workers) as pool:
            batch_size = 5000
            for batch_start in range(0, len(tasks), batch_size):
                batch = tasks[batch_start:batch_start + batch_size]
                results = pool.map(process_entry, batch)

                for result, status in results:
                    if status == 'ok' and result:
                        entity_type, data = result
                        files[entity_type].write(json.dumps(data, ensure_ascii=False) + '\n')
                        stats[entity_type + 's'] += 1
                    else:
                        stats[status] = stats.get(status, 0) + 1

                processed = batch_start + len(batch)
                pct = processed / len(tasks) * 100
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (len(tasks) - processed) / rate / 60 if rate > 0 else 0

                print(f"[{processed:,}/{len(tasks):,} ({pct:.1f}%)] "
                      f"P:{stats['persons']:,} L:{stats['locations']:,} E:{stats['events']:,} "
                      f"({rate:.0f}/s, ETA:{eta:.0f}min)", flush=True)

                for f in files.values():
                    f.flush()
                with open(CHECKPOINT_FILE, 'w') as f:
                    json.dump({'last_index': start_index + processed, 'stats': stats}, f)

    finally:
        for f in files.values():
            f.close()

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print("-" * 60, flush=True)
    print(f"Completed in {elapsed:.1f} minutes!", flush=True)
    print(json.dumps(stats, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Parallel Wikipedia extraction")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--no-resume", action="store_true")

    args = parser.parse_args()

    limit = None if args.full else (args.limit or 100000)
    extract_parallel(num_workers=args.workers, limit=limit, resume=not args.no_resume)


if __name__ == "__main__":
    main()
