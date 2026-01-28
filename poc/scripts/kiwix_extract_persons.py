"""
Wikipedia → DB 역방향 추출
Wikipedia ZIM에서 모든 역사적 인물을 추출

역사적 인물 기준:
- 사망년도가 있음 (살아있는 사람 제외)
- 또는 생년이 1900년 이전

Usage:
    python kiwix_extract_persons.py --limit 100000    # 10만개 테스트
    python kiwix_extract_persons.py --resume          # 이어서
    python kiwix_extract_persons.py --full            # 전체 (1900만)
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
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_persons"
CHECKPOINT_FILE = OUTPUT_DIR / "extract_checkpoint.json"
PERSONS_JSONL = OUTPUT_DIR / "persons.jsonl"

# Lazy loading
_archive = None


def get_archive() -> Archive:
    global _archive
    if _archive is None:
        _archive = Archive(str(ZIM_PATH))
    return _archive


# ============ HTML Parser ============

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'sup', 'sub'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self):
        return ' '.join(self.text_parts)


def html_to_text(html: str) -> str:
    parser = HTMLTextExtractor()
    try:
        parser.feed(html)
    except:
        pass
    return parser.get_text()


# ============ Person Detection ============

def is_person_article(html: str) -> bool:
    """인물 문서인지 감지 - 속도 최적화"""
    html_lower = html[:80000].lower()

    # 1. 빠른 키워드 필터 (HTML에서 직접)
    # Personal details + Born 조합이면 거의 확실히 인물
    if 'personal details' in html_lower and '>born<' in html_lower:
        return True

    # 2. Infobox 패턴 (빠름)
    person_infoboxes = [
        'infobox biography', 'infobox person', 'infobox military person',
        'infobox philosopher', 'infobox scientist', 'infobox writer',
        'infobox politician', 'infobox monarch', 'infobox royalty',
        'infobox officeholder', 'infobox emperor',
    ]
    for pattern in person_infoboxes:
        if pattern in html_lower:
            return True

    # 3. 첫 부분에서 인물 패턴 (HTML에서 직접 - 파싱 없이)
    first_5000 = html_lower[:5000]

    # (년도–년도) + was a/an 패턴
    if re.search(r'\(\d{4}\s*[–\-–]\s*\d{4}\)', first_5000):
        if ' was a ' in first_5000 or ' was an ' in first_5000 or ' is a ' in first_5000:
            return True

    # 4. 직업 키워드 (빠른 체크)
    occupations = ['politician', 'emperor', 'king', 'queen', 'general', 'philosopher',
                   'scientist', 'writer', 'poet', 'composer', 'artist', 'president',
                   'pope', 'bishop', 'duke', 'earl', 'baron', 'sultan', 'pharaoh']

    for occ in occupations:
        if f'was a {occ}' in first_5000 or f'was an {occ}' in first_5000:
            return True
        if f'is a {occ}' in first_5000 or f'is an {occ}' in first_5000:
            return True

    return False


def is_historical_person(birth_year: Optional[int], death_year: Optional[int]) -> bool:
    """역사적 인물인지 (사망했거나 오래된 인물)"""
    if death_year:
        return True
    if birth_year and birth_year < 1925:  # 100세 이상
        return True
    return False


def extract_wikidata_qid(html: str) -> Optional[str]:
    """Wikidata QID 추출"""
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    return match.group(1) if match else None


def extract_birth_death(html: str) -> Tuple[Optional[int], Optional[int]]:
    """생몰년 추출"""
    text = html_to_text(html[:5000])

    patterns = [
        # (February 12, 1809 – April 15, 1865) - 풀 날짜 형식
        r'\([^)]*?(\d{4})[^)]*?[–\-][^)]*?(\d{4})[^)]*?\)',
        # (1769 – 1821)
        r'\((\d{3,4})\s*[–\-]\s*(\d{3,4})\)',
        # (c. 1412 – 1431)
        r'\(c\.?\s*(\d{3,4})\s*[–\-]\s*(\d{3,4})\)',
        # Born ( 1809-02-12 ) ... Died ... 1865
        r'Born[^0-9]*(\d{4}).*?Died[^0-9]*(\d{4})',
        # (born 1769, died 1821)
        r'born[:\s]+(\d{3,4}).*?died[:\s]+(\d{3,4})',
        # BCE dates
        r'\((\d{3,4})\s*BC[E]?\s*[–\-]\s*(\d{3,4})\s*BC[E]?\)',
        r'(\d{3,4})\s*BC[E]?\s*[–\-]\s*(\d{3,4})\s*BC[E]?',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            groups = match.groups()
            try:
                birth = int(groups[0]) if groups[0] else None
                death = int(groups[1]) if len(groups) > 1 and groups[1] else None
            except:
                continue

            # BCE 처리
            if 'BC' in pattern.upper():
                birth = -birth if birth else None
                death = -death if death else None

            # 유효성 검사 (너무 큰 숫자 제외)
            if birth and (birth < -5000 or birth > 2030):
                continue
            if death and (death < -5000 or death > 2030):
                continue

            return birth, death

    return None, None


def extract_first_sentence(html: str) -> str:
    """첫 문장 추출 (요약)"""
    text = html_to_text(html[:3000])

    # 첫 문장 찾기
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if sentences:
        first = sentences[0].strip()
        # 너무 짧으면 두 문장
        if len(first) < 50 and len(sentences) > 1:
            first = first + ' ' + sentences[1].strip()
        return first[:500]

    return ""


def extract_categories(html: str) -> list[str]:
    """카테고리 추출"""
    categories = []

    # 카테고리 링크 패턴
    cat_matches = re.findall(r'title="Category:([^"]+)"', html)
    for cat in cat_matches[:10]:  # 최대 10개
        categories.append(cat.replace('_', ' '))

    return categories


# ============ Data Class ============

@dataclass
class WikiPerson:
    """Wikipedia에서 추출한 인물"""
    title: str
    qid: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    summary: str
    categories: list[str]
    wikipedia_path: str


# ============ Main Processing ============

def load_checkpoint() -> Tuple[int, dict]:
    """체크포인트 로드"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('last_index', 0), data.get('stats', {})
    return 0, {}


def save_checkpoint(index: int, stats: dict):
    """체크포인트 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'last_index': index, 'stats': stats}, f)


def append_person(person: WikiPerson):
    """인물 추가"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PERSONS_JSONL, 'a', encoding='utf-8') as f:
        f.write(json.dumps(asdict(person), ensure_ascii=False) + '\n')


def extract_persons(limit: int = 100000, resume: bool = True):
    """Wikipedia에서 인물 추출"""
    zim = get_archive()
    total_entries = zim.entry_count

    # 체크포인트
    start_index, stats = load_checkpoint() if resume else (0, {})

    if not stats:
        stats = {
            'scanned': 0,
            'persons_found': 0,
            'historical_persons': 0,
            'with_qid': 0,
            'skipped_redirect': 0,
            'skipped_non_article': 0,
        }

    print(f"Wikipedia ZIM: {total_entries:,} entries")
    print(f"Starting from index: {start_index:,}")
    print(f"Limit: {limit:,}")
    print("-" * 60)

    end_index = min(start_index + limit, total_entries)

    for i in range(start_index, end_index):
        try:
            entry = zim._get_entry_by_id(i)
            stats['scanned'] += 1

            # 리다이렉트 스킵
            if entry.is_redirect:
                stats['skipped_redirect'] += 1
                continue

            # 문서만 (리소스 파일 제외)
            path = entry.path
            if path.startswith('_') or path.startswith('-') or '/' in path:
                stats['skipped_non_article'] += 1
                continue

            # HTML 가져오기
            try:
                item = entry.get_item()
                html = bytes(item.content).decode('utf-8', errors='ignore')
            except:
                continue

            # 인물 문서인지 확인
            if not is_person_article(html):
                continue

            stats['persons_found'] += 1

            # 생몰년 추출
            birth, death = extract_birth_death(html)

            # 역사적 인물인지 확인
            if not is_historical_person(birth, death):
                continue

            stats['historical_persons'] += 1

            # QID 추출
            qid = extract_wikidata_qid(html)
            if qid:
                stats['with_qid'] += 1

            # 인물 데이터 생성
            person = WikiPerson(
                title=entry.title,
                qid=qid,
                birth_year=birth,
                death_year=death,
                summary=extract_first_sentence(html),
                categories=extract_categories(html),
                wikipedia_path=path,
            )

            # 저장
            append_person(person)

            # 진행 상황 (1000개마다)
            if stats['historical_persons'] % 1000 == 0 and stats['historical_persons'] > 0:
                print(f"[{i:,}/{end_index:,}] Found {stats['historical_persons']:,} historical persons (QID: {stats['with_qid']:,})", flush=True)

        except Exception as e:
            continue

        # 체크포인트 (10000개마다)
        if (i - start_index + 1) % 10000 == 0:
            save_checkpoint(i + 1, stats)
            print(f"  [Checkpoint at {i+1:,}] Scanned: {stats['scanned']:,}, Persons: {stats['historical_persons']:,}", flush=True)

    # 최종 체크포인트
    save_checkpoint(end_index, stats)

    print("-" * 60)
    print("Completed!")
    print(json.dumps(stats, indent=2))


def show_stats():
    """현재 통계"""
    _, stats = load_checkpoint()
    print("Current stats:")
    print(json.dumps(stats, indent=2))

    if PERSONS_JSONL.exists():
        with open(PERSONS_JSONL, 'r', encoding='utf-8') as f:
            count = sum(1 for _ in f)
        print(f"\nPersons in JSONL: {count:,}")


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(description="Extract persons from Wikipedia ZIM")
    parser.add_argument("--limit", type=int, default=100000, help="Number of entries to scan")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--full", action="store_true", help="Process all entries")
    parser.add_argument("--stats", action="store_true", help="Show stats")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    limit = 20000000 if args.full else args.limit  # 전체는 2천만

    extract_persons(limit=limit, resume=args.resume)


if __name__ == "__main__":
    main()
