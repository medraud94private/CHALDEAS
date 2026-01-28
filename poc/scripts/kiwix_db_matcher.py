"""
Kiwix-DB Matcher - CHALDEAS DB와 Wikipedia/Wikisource 대조 도구

기능:
1. DB persons ↔ Wikipedia 매칭 (wikidata_id, wikipedia_url, name)
2. 매칭된 문서에서 추가 정보 추출
3. 미매칭 엔티티 리포트
4. Wikipedia → DB 역방향 검색

Usage:
    python kiwix_db_matcher.py match-persons --limit 100
    python kiwix_db_matcher.py enrich-person "Napoleon"
    python kiwix_db_matcher.py find-missing --type persons
    python kiwix_db_matcher.py reverse-search "Joan of Arc"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# 프로젝트 경로 설정
BACKEND_PATH = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from libzim.reader import Archive
from html.parser import HTMLParser


# ============ Config ============

ZIM_DIR = Path(__file__).parent.parent.parent / "data" / "kiwix"
ZIM_FILES = {
    "wikipedia": ZIM_DIR / "wikipedia_en_nopic.zim",
    "wikisource": ZIM_DIR / "wikisource_en_nopic.zim",
    "wikiquote": ZIM_DIR / "wikiquote_en_nopic.zim",
}

# Lazy loading
_archives = {}


def get_archive(source: str = "wikipedia") -> Archive:
    """ZIM 아카이브 (캐시됨)"""
    if source not in _archives:
        path = ZIM_FILES.get(source)
        if not path or not path.exists():
            raise FileNotFoundError(f"ZIM not found: {path}")
        _archives[source] = Archive(str(path))
    return _archives[source]


# ============ HTML Parser ============

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'sup'}
        self.current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.current_skip > 0:
            self.current_skip -= 1
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        if self.current_skip == 0:
            self.text_parts.append(data)

    def get_text(self):
        text = ''.join(self.text_parts)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()


def html_to_text(html: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ============ Wikipedia Access ============

def get_article_html(title: str, source: str = "wikipedia") -> Optional[str]:
    """문서 HTML 가져오기"""
    zim = get_archive(source)

    paths_to_try = [
        f"A/{title}",
        f"A/{title.replace(' ', '_')}",
        title,
        title.replace(' ', '_'),
    ]

    for path in paths_to_try:
        try:
            entry = zim.get_entry_by_path(path)
            if entry.is_redirect:
                entry = entry.get_redirect_entry()
            item = entry.get_item()
            return bytes(item.content).decode('utf-8')
        except (KeyError, RuntimeError):
            continue

    return None


def extract_wikidata_qid(html: str) -> Optional[str]:
    """HTML에서 Wikidata QID 추출"""
    match = re.search(r'wikidata\.org/wiki/(Q\d+)', html)
    if match:
        return match.group(1)
    return None


def extract_wikipedia_url(html: str) -> Optional[str]:
    """HTML에서 canonical Wikipedia URL 추출"""
    match = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    if match:
        return match.group(1)
    return None


def extract_first_paragraph(html: str) -> str:
    """첫 번째 문단 추출 (요약)"""
    text = html_to_text(html)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 50]
    return paragraphs[0] if paragraphs else ""


def extract_birth_death_years(html: str) -> tuple[Optional[int], Optional[int]]:
    """생몰년 추출"""
    text = html_to_text(html)
    first_para = text[:500]

    # 패턴: (1769–1821), (c. 1412 – 1431), (born 1950)
    patterns = [
        r'\((\d{1,4})\s*[–-]\s*(\d{1,4})\)',  # (1769–1821)
        r'\(c\.\s*(\d{1,4})\s*[–-]\s*(\d{1,4})\)',  # (c. 1412 – 1431)
        r'\(born\s+(\d{4})',  # (born 1950)
        r'\((\d{1,4})\s*BC\s*[–-]\s*(\d{1,4})\s*BC\)',  # BCE
    ]

    for pattern in patterns:
        match = re.search(pattern, first_para)
        if match:
            groups = match.groups()
            birth = int(groups[0]) if groups[0] else None
            death = int(groups[1]) if len(groups) > 1 and groups[1] else None

            # BC 처리
            if 'BC' in pattern:
                birth = -birth if birth else None
                death = -death if death else None

            return birth, death

    return None, None


# ============ Data Classes ============

@dataclass
class WikipediaMatch:
    """Wikipedia 매칭 결과"""
    db_id: int
    db_name: str
    db_wikidata_id: Optional[str]
    wiki_title: Optional[str]
    wiki_qid: Optional[str]
    wiki_url: Optional[str]
    match_type: str  # 'wikidata_id', 'wikipedia_url', 'name', 'not_found'
    summary: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None


@dataclass
class EnrichmentData:
    """보강 데이터"""
    wikidata_id: Optional[str]
    wikipedia_url: Optional[str]
    summary: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    quotes: list[str]


# ============ Matching Functions ============

def match_person_by_wikidata_id(qid: str) -> Optional[str]:
    """Wikidata QID로 Wikipedia 문서 찾기 (전체 스캔 필요 - 느림)"""
    # 일단 skip - 너무 느림
    return None


def match_person_by_name(name: str) -> Optional[tuple[str, str]]:
    """이름으로 Wikipedia 문서 찾기"""
    html = get_article_html(name)
    if html:
        qid = extract_wikidata_qid(html)
        return name, qid
    return None


def match_db_person(person) -> WikipediaMatch:
    """DB Person과 Wikipedia 매칭"""
    result = WikipediaMatch(
        db_id=person.id,
        db_name=person.name,
        db_wikidata_id=person.wikidata_id,
        wiki_title=None,
        wiki_qid=None,
        wiki_url=None,
        match_type='not_found'
    )

    # 1. wikipedia_url로 매칭
    if person.wikipedia_url:
        # URL에서 제목 추출
        match = re.search(r'wikipedia\.org/wiki/(.+)$', person.wikipedia_url)
        if match:
            title = match.group(1).replace('_', ' ')
            html = get_article_html(title)
            if html:
                result.wiki_title = title
                result.wiki_qid = extract_wikidata_qid(html)
                result.wiki_url = extract_wikipedia_url(html)
                result.match_type = 'wikipedia_url'
                result.summary = extract_first_paragraph(html)[:300]
                result.birth_year, result.death_year = extract_birth_death_years(html)
                return result

    # 2. 이름으로 매칭
    html = get_article_html(person.name)
    if html:
        result.wiki_title = person.name
        result.wiki_qid = extract_wikidata_qid(html)
        result.wiki_url = extract_wikipedia_url(html)
        result.match_type = 'name'
        result.summary = extract_first_paragraph(html)[:300]
        result.birth_year, result.death_year = extract_birth_death_years(html)
        return result

    return result


def enrich_person_from_wikipedia(name: str) -> Optional[EnrichmentData]:
    """Wikipedia에서 인물 정보 추출"""
    html = get_article_html(name)
    if not html:
        return None

    birth, death = extract_birth_death_years(html)

    # Wikiquote에서 명언
    quotes = []
    quote_html = get_article_html(name, source="wikiquote")
    if quote_html:
        quote_text = html_to_text(quote_html)
        for line in quote_text.split('\n'):
            line = line.strip()
            if line and len(line) > 30 and not line.startswith('='):
                quotes.append(line)
                if len(quotes) >= 5:
                    break

    return EnrichmentData(
        wikidata_id=extract_wikidata_qid(html),
        wikipedia_url=extract_wikipedia_url(html),
        summary=extract_first_paragraph(html),
        birth_year=birth,
        death_year=death,
        quotes=quotes,
    )


def reverse_search_wikipedia(wiki_title: str) -> Optional[dict]:
    """Wikipedia 문서 → DB 엔티티 역방향 검색"""
    html = get_article_html(wiki_title)
    if not html:
        return None

    qid = extract_wikidata_qid(html)
    wiki_url = extract_wikipedia_url(html)

    # DB 연결
    from app.db.session import SessionLocal
    from app.models import Person, Event

    db = SessionLocal()
    try:
        # wikidata_id로 검색
        if qid:
            person = db.query(Person).filter(Person.wikidata_id == qid).first()
            if person:
                return {
                    "found": True,
                    "type": "person",
                    "match_by": "wikidata_id",
                    "db_id": person.id,
                    "db_name": person.name,
                    "wiki_qid": qid,
                }

        # wikipedia_url로 검색
        if wiki_url:
            person = db.query(Person).filter(Person.wikipedia_url == wiki_url).first()
            if person:
                return {
                    "found": True,
                    "type": "person",
                    "match_by": "wikipedia_url",
                    "db_id": person.id,
                    "db_name": person.name,
                    "wiki_qid": qid,
                }

        # 이름으로 검색
        person = db.query(Person).filter(Person.name.ilike(wiki_title)).first()
        if person:
            return {
                "found": True,
                "type": "person",
                "match_by": "name",
                "db_id": person.id,
                "db_name": person.name,
                "wiki_qid": qid,
            }

        return {
            "found": False,
            "wiki_title": wiki_title,
            "wiki_qid": qid,
            "wiki_url": wiki_url,
            "summary": extract_first_paragraph(html)[:200],
        }

    finally:
        db.close()


# ============ Batch Operations ============

def match_all_persons(limit: int = 100, offset: int = 0) -> list[WikipediaMatch]:
    """DB의 모든 persons와 Wikipedia 매칭"""
    from app.db.session import SessionLocal
    from app.models import Person

    db = SessionLocal()
    results = []

    try:
        persons = db.query(Person).order_by(Person.id).offset(offset).limit(limit).all()

        for i, person in enumerate(persons):
            print(f"[{i+1}/{len(persons)}] {person.name}...", end=" ", flush=True)
            match = match_db_person(person)
            results.append(match)
            print(f"→ {match.match_type}" + (f" (QID: {match.wiki_qid})" if match.wiki_qid else ""))

    finally:
        db.close()

    return results


def find_missing_wikidata(entity_type: str = "persons", limit: int = 100) -> list[dict]:
    """Wikidata ID가 없는 엔티티 찾기"""
    from app.db.session import SessionLocal
    from app.models import Person

    if entity_type != "persons":
        raise ValueError("Currently only 'persons' supported")

    db = SessionLocal()
    missing = []

    try:
        persons = db.query(Person).filter(
            (Person.wikidata_id == None) | (Person.wikidata_id == "")
        ).limit(limit).all()

        for person in persons:
            html = get_article_html(person.name)
            if html:
                qid = extract_wikidata_qid(html)
                if qid:
                    missing.append({
                        "db_id": person.id,
                        "db_name": person.name,
                        "suggested_qid": qid,
                        "source": "wikipedia_name_match",
                    })

    finally:
        db.close()

    return missing


def generate_match_report(matches: list[WikipediaMatch]) -> dict:
    """매칭 결과 리포트 생성"""
    total = len(matches)
    by_type = {}
    for m in matches:
        by_type[m.match_type] = by_type.get(m.match_type, 0) + 1

    not_found = [m for m in matches if m.match_type == 'not_found']
    qid_mismatch = [m for m in matches if m.db_wikidata_id and m.wiki_qid and m.db_wikidata_id != m.wiki_qid]

    return {
        "total": total,
        "by_match_type": by_type,
        "match_rate": f"{(total - len(not_found)) / total * 100:.1f}%",
        "not_found_count": len(not_found),
        "not_found_samples": [{"id": m.db_id, "name": m.db_name} for m in not_found[:10]],
        "qid_mismatch_count": len(qid_mismatch),
        "qid_mismatches": [
            {"id": m.db_id, "name": m.db_name, "db_qid": m.db_wikidata_id, "wiki_qid": m.wiki_qid}
            for m in qid_mismatch
        ],
    }


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(description="Kiwix-DB Matcher")
    subparsers = parser.add_subparsers(dest="command")

    # match-persons
    mp = subparsers.add_parser("match-persons", help="Match DB persons with Wikipedia")
    mp.add_argument("--limit", type=int, default=100)
    mp.add_argument("--offset", type=int, default=0)
    mp.add_argument("--output", "-o", help="Output JSON file")

    # enrich-person
    ep = subparsers.add_parser("enrich-person", help="Get enrichment data for a person")
    ep.add_argument("name", help="Person name")

    # find-missing
    fm = subparsers.add_parser("find-missing", help="Find entities missing Wikidata ID")
    fm.add_argument("--type", default="persons", choices=["persons"])
    fm.add_argument("--limit", type=int, default=100)
    fm.add_argument("--output", "-o", help="Output JSON file")

    # reverse-search
    rs = subparsers.add_parser("reverse-search", help="Search DB from Wikipedia title")
    rs.add_argument("title", help="Wikipedia article title")

    args = parser.parse_args()

    # UTF-8 출력
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')

    if args.command == "match-persons":
        matches = match_all_persons(args.limit, args.offset)
        report = generate_match_report(matches)

        print("\n=== Match Report ===")
        print(json.dumps(report, indent=2, ensure_ascii=False))

        if args.output:
            data = {
                "matches": [asdict(m) for m in matches],
                "report": report,
            }
            Path(args.output).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"\nSaved to {args.output}")

    elif args.command == "enrich-person":
        data = enrich_person_from_wikipedia(args.name)
        if data:
            print(f"=== {args.name} ===")
            print(f"Wikidata ID: {data.wikidata_id}")
            print(f"Wikipedia: {data.wikipedia_url}")
            print(f"Birth/Death: {data.birth_year} - {data.death_year}")
            print(f"\nSummary:\n{data.summary[:500]}...")
            if data.quotes:
                print(f"\nQuotes:")
                for q in data.quotes:
                    print(f"  - {q[:100]}...")
        else:
            print(f"Not found: {args.name}")

    elif args.command == "find-missing":
        missing = find_missing_wikidata(args.type, args.limit)
        print(f"Found {len(missing)} entities with suggested Wikidata IDs:\n")
        for item in missing[:20]:
            print(f"  [{item['db_id']}] {item['db_name']} → {item['suggested_qid']}")

        if args.output:
            Path(args.output).write_text(json.dumps(missing, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"\nSaved to {args.output}")

    elif args.command == "reverse-search":
        result = reverse_search_wikipedia(args.title)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Wikipedia article not found: {args.title}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
