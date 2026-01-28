"""
Wikipedia-DB Linker - 추출된 Wikipedia 데이터를 DB와 연결

기능:
1. 추출된 persons/locations/events JSONL을 DB와 매칭 (QID 또는 이름)
2. Wikipedia Source 레코드 생성
3. 원본 HTML에서 내부 링크 추출하여 관계 등록
4. 체크포인트 지원 (중단 시 재개 가능)

Usage:
    python link_wikipedia_to_db.py --type persons --limit 1000
    python link_wikipedia_to_db.py --type all --resume
    python link_wikipedia_to_db.py --stats
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import argparse
from pathlib import Path
from typing import Optional, Set, Dict, List
from dataclasses import dataclass
from html.parser import HTMLParser

# 프로젝트 경로 설정
BACKEND_PATH = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from libzim.reader import Archive

# ============ Config ============

ZIM_PATH = Path(__file__).parent.parent.parent / "data" / "kiwix" / "wikipedia_en_nopic.zim"
EXTRACT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_extract"
CHECKPOINT_FILE = EXTRACT_DIR / "linker_checkpoint.json"

CHECKPOINT_INTERVAL = 100  # DB 작업이므로 더 자주 저장

_archive = None

# ============ Entity Cache (최적화) ============
_person_cache: Dict[str, Optional[int]] = {}  # name -> person_id
_event_cache: Dict[str, Optional[int]] = {}   # title -> event_id
_location_cache: Dict[str, Optional[int]] = {}  # name -> location_id
CACHE_SIZE_LIMIT = 50000


def get_archive() -> Archive:
    global _archive
    if _archive is None:
        _archive = Archive(str(ZIM_PATH))
    return _archive


# ============ Internal Link Extractor ============

class WikiLinkExtractor(HTMLParser):
    """Wikipedia 내부 링크 추출기"""

    def __init__(self):
        super().__init__()
        self.links: List[str] = []
        self.in_content = False
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # 본문 영역 감지
        if tag == 'div' and attrs_dict.get('id') == 'mw-content-text':
            self.in_content = True

        # 건너뛸 영역 (navbox, sidebar 등)
        if tag in ('nav', 'aside') or 'navbox' in attrs_dict.get('class', ''):
            self.skip_depth += 1
            return

        # 내부 링크 추출
        if self.in_content and self.skip_depth == 0 and tag == 'a':
            href = attrs_dict.get('href', '')
            if not href:
                return
            # 외부 링크, 앵커, 특수 경로 제외
            if href.startswith(('http', 'https', '#', '_', 'mailto:')):
                return
            # 특수 페이지 제외 (ZIM 형식은 /wiki/ 없이 바로 시작하기도 함)
            skip_prefixes = ('Special:', 'File:', 'Help:', 'Category:', 'Template:', 'Wikipedia:', 'Talk:', 'Portal:', 'User:')
            if any(href.startswith(p) or ('/' + p) in href for p in skip_prefixes):
                return
            # 경로 정규화
            link = href.replace('/wiki/', '').replace('./', '')
            link = link.split('#')[0]  # 앵커 제거
            if link and ':' not in link:  # 네임스페이스 제외
                self.links.append(link)

    def handle_endtag(self, tag):
        if tag in ('nav', 'aside') and self.skip_depth > 0:
            self.skip_depth -= 1


def extract_internal_links(html: str, limit: int = 50) -> List[str]:
    """HTML에서 내부 Wikipedia 링크 추출"""
    parser = WikiLinkExtractor()
    try:
        parser.feed(html[:200000])  # 처음 200KB만
    except:
        pass

    # 중복 제거, 순서 유지
    seen = set()
    unique_links = []
    for link in parser.links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
            if len(unique_links) >= limit:
                break

    return unique_links


def get_article_html(path: str) -> Optional[str]:
    """Wikipedia 문서 HTML 가져오기"""
    zim = get_archive()

    paths_to_try = [path, f"A/{path}", path.replace('_', ' ')]

    for p in paths_to_try:
        try:
            entry = zim.get_entry_by_path(p)
            if entry.is_redirect:
                entry = entry.get_redirect_entry()
            item = entry.get_item()
            return bytes(item.content).decode('utf-8', errors='ignore')
        except:
            continue

    return None


# ============ DB Operations ============

def get_db_session():
    from app.db.session import SessionLocal
    return SessionLocal()


def batch_find_persons(db, names: List[str]) -> Dict[str, int]:
    """배치로 여러 인물 한번에 조회 (최적화)"""
    global _person_cache
    from app.models import Person
    from sqlalchemy import func

    result = {}
    uncached_names = []

    # 캐시에서 먼저 찾기
    for name in names:
        name_lower = name.lower()
        if name_lower in _person_cache:
            if _person_cache[name_lower] is not None:
                result[name] = _person_cache[name_lower]
        else:
            uncached_names.append(name)

    if not uncached_names:
        return result

    # DB 배치 조회 (대소문자 무시)
    persons = db.query(Person.id, Person.name).filter(
        func.lower(Person.name).in_([n.lower() for n in uncached_names])
    ).all()

    # 결과 처리 및 캐시 저장
    found_names = {}
    for person_id, person_name in persons:
        found_names[person_name.lower()] = person_id

    for name in uncached_names:
        name_lower = name.lower()
        if name_lower in found_names:
            result[name] = found_names[name_lower]
            _person_cache[name_lower] = found_names[name_lower]
        else:
            _person_cache[name_lower] = None

    # 캐시 크기 관리
    if len(_person_cache) > CACHE_SIZE_LIMIT:
        _person_cache.clear()

    return result


def batch_find_events(db, titles: List[str]) -> Dict[str, int]:
    """배치로 여러 이벤트 한번에 조회 (최적화)"""
    global _event_cache
    from app.models import Event
    from sqlalchemy import func

    result = {}
    uncached_titles = []

    for title in titles:
        title_lower = title.lower()
        if title_lower in _event_cache:
            if _event_cache[title_lower] is not None:
                result[title] = _event_cache[title_lower]
        else:
            uncached_titles.append(title)

    if not uncached_titles:
        return result

    events = db.query(Event.id, Event.title).filter(
        func.lower(Event.title).in_([t.lower() for t in uncached_titles])
    ).all()

    found_titles = {}
    for event_id, event_title in events:
        found_titles[event_title.lower()] = event_id

    for title in uncached_titles:
        title_lower = title.lower()
        if title_lower in found_titles:
            result[title] = found_titles[title_lower]
            _event_cache[title_lower] = found_titles[title_lower]
        else:
            _event_cache[title_lower] = None

    if len(_event_cache) > CACHE_SIZE_LIMIT:
        _event_cache.clear()

    return result


def batch_find_locations(db, names: List[str]) -> Dict[str, int]:
    """배치로 여러 장소 한번에 조회 (최적화)"""
    global _location_cache
    from app.models import Location
    from sqlalchemy import func

    result = {}
    uncached_names = []

    for name in names:
        name_lower = name.lower()
        if name_lower in _location_cache:
            if _location_cache[name_lower] is not None:
                result[name] = _location_cache[name_lower]
        else:
            uncached_names.append(name)

    if not uncached_names:
        return result

    locations = db.query(Location.id, Location.name).filter(
        func.lower(Location.name).in_([n.lower() for n in uncached_names])
    ).all()

    found_names = {}
    for loc_id, loc_name in locations:
        found_names[loc_name.lower()] = loc_id

    for name in uncached_names:
        name_lower = name.lower()
        if name_lower in found_names:
            result[name] = found_names[name_lower]
            _location_cache[name_lower] = found_names[name_lower]
        else:
            _location_cache[name_lower] = None

    if len(_location_cache) > CACHE_SIZE_LIMIT:
        _location_cache.clear()

    return result


def find_person_in_db(db, qid: Optional[str], name: str):
    """DB에서 인물 찾기"""
    from app.models import Person

    # 1. QID로 찾기
    if qid:
        person = db.query(Person).filter(Person.wikidata_id == qid).first()
        if person:
            return person, 'qid'

    # 2. 정확한 이름으로 찾기
    person = db.query(Person).filter(Person.name == name).first()
    if person:
        return person, 'exact_name'

    # 3. 대소문자 무시 이름
    person = db.query(Person).filter(Person.name.ilike(name)).first()
    if person:
        return person, 'ilike_name'

    return None, None


def find_location_in_db(db, qid: Optional[str], name: str):
    """DB에서 장소 찾기"""
    from app.models import Location

    if qid:
        loc = db.query(Location).filter(Location.wikidata_id == qid).first()
        if loc:
            return loc, 'qid'

    loc = db.query(Location).filter(Location.name == name).first()
    if loc:
        return loc, 'exact_name'

    loc = db.query(Location).filter(Location.name.ilike(name)).first()
    if loc:
        return loc, 'ilike_name'

    return None, None


def find_event_in_db(db, qid: Optional[str], name: str):
    """DB에서 이벤트 찾기"""
    from app.models import Event

    if qid:
        event = db.query(Event).filter(Event.wikidata_id == qid).first()
        if event:
            return event, 'qid'

    # Event 테이블은 name이 아닌 title 사용
    event = db.query(Event).filter(Event.title == name).first()
    if event:
        return event, 'exact_name'

    event = db.query(Event).filter(Event.title.ilike(name)).first()
    if event:
        return event, 'ilike_name'

    return None, None


def get_or_create_wikipedia_source(db, title: str, path: str, qid: Optional[str]) -> int:
    """Wikipedia Source 레코드 생성 또는 가져오기"""
    from app.models import Source

    url = f"https://en.wikipedia.org/wiki/{path}"

    # 기존 소스 찾기
    source = db.query(Source).filter(Source.url == url).first()
    if source:
        return source.id

    # 새 소스 생성
    source = Source(
        name=f"Wikipedia: {title}",
        type="digital_archive",
        url=url,
        archive_type="wikipedia",
        document_id=qid,
        document_path=path,
        title=title,
        language="en",
    )
    db.add(source)
    db.flush()

    return source.id


def link_person_to_source(db, person_id: int, source_id: int):
    """Person-Source 연결"""
    from app.models.associations import person_sources

    # 중복 체크
    exists = db.execute(
        person_sources.select().where(
            (person_sources.c.person_id == person_id) &
            (person_sources.c.source_id == source_id)
        )
    ).first()

    if not exists:
        db.execute(person_sources.insert().values(
            person_id=person_id,
            source_id=source_id
        ))


def link_event_to_source(db, event_id: int, source_id: int):
    """Event-Source 연결"""
    from app.models.associations import event_sources

    exists = db.execute(
        event_sources.select().where(
            (event_sources.c.event_id == event_id) &
            (event_sources.c.source_id == source_id)
        )
    ).first()

    if not exists:
        db.execute(event_sources.insert().values(
            event_id=event_id,
            source_id=source_id
        ))


def link_person_to_person(db, person_id: int, related_person_id: int, rel_type: str = "mentioned_with", bidirectional: bool = True):
    """Person-Person 관계 등록 (상호링크 지원)"""
    from app.models.associations import person_relationships

    if person_id == related_person_id:
        return 0

    links_created = 0

    # A→B 방향
    exists = db.execute(
        person_relationships.select().where(
            (person_relationships.c.person_id == person_id) &
            (person_relationships.c.related_person_id == related_person_id)
        )
    ).first()

    if not exists:
        db.execute(person_relationships.insert().values(
            person_id=person_id,
            related_person_id=related_person_id,
            relationship_type=rel_type,
            strength=2,  # Wikipedia 링크는 약한 관계
            confidence=0.5,
        ))
        links_created += 1

    # B→A 방향 (상호링크)
    if bidirectional:
        exists_reverse = db.execute(
            person_relationships.select().where(
                (person_relationships.c.person_id == related_person_id) &
                (person_relationships.c.related_person_id == person_id)
            )
        ).first()

        if not exists_reverse:
            db.execute(person_relationships.insert().values(
                person_id=related_person_id,
                related_person_id=person_id,
                relationship_type=rel_type,
                strength=2,
                confidence=0.5,
            ))
            links_created += 1

    return links_created


def link_event_to_person(db, event_id: int, person_id: int, role: str = "mentioned"):
    """Event-Person 관계 등록"""
    from app.models.associations import event_persons

    exists = db.execute(
        event_persons.select().where(
            (event_persons.c.event_id == event_id) &
            (event_persons.c.person_id == person_id)
        )
    ).first()

    if not exists:
        db.execute(event_persons.insert().values(
            event_id=event_id,
            person_id=person_id,
            role=role
        ))


def link_event_to_event(db, from_event_id: int, to_event_id: int, rel_type: str = "related_to"):
    """Event-Event 관계 등록"""
    from app.models.associations import event_relationships

    if from_event_id == to_event_id:
        return

    exists = db.execute(
        event_relationships.select().where(
            (event_relationships.c.from_event_id == from_event_id) &
            (event_relationships.c.to_event_id == to_event_id)
        )
    ).first()

    if not exists:
        db.execute(event_relationships.insert().values(
            from_event_id=from_event_id,
            to_event_id=to_event_id,
            relationship_type=rel_type,
            strength=2,
            confidence=0.5,
        ))


def link_location_to_person(db, location_id: int, person_id: int, role: str = "mentioned"):
    """Location-Person 관계 등록"""
    from app.models.associations import person_locations

    exists = db.execute(
        person_locations.select().where(
            (person_locations.c.person_id == person_id) &
            (person_locations.c.location_id == location_id)
        )
    ).first()

    if not exists:
        db.execute(person_locations.insert().values(
            person_id=person_id,
            location_id=location_id,
            role=role,
            confidence=0.5
        ))


def link_location_to_event(db, location_id: int, event_id: int):
    """Location-Event 관계 등록"""
    from app.models.associations import event_locations

    exists = db.execute(
        event_locations.select().where(
            (event_locations.c.event_id == event_id) &
            (event_locations.c.location_id == location_id)
        )
    ).first()

    if not exists:
        db.execute(event_locations.insert().values(
            event_id=event_id,
            location_id=location_id,
            role="mentioned"
        ))


def link_location_to_location(db, location_id: int, related_location_id: int, rel_type: str = "related_to"):
    """Location-Location 관계 등록"""
    from app.models.associations import location_relationships

    if location_id == related_location_id:
        return

    exists = db.execute(
        location_relationships.select().where(
            (location_relationships.c.location_id == location_id) &
            (location_relationships.c.related_location_id == related_location_id)
        )
    ).first()

    if not exists:
        db.execute(location_relationships.insert().values(
            location_id=location_id,
            related_location_id=related_location_id,
            relationship_type=rel_type,
            strength=2,
            confidence=0.5
        ))


# ============ Checkpoint ============

def load_checkpoint() -> Dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'persons': {'processed': 0, 'matched': 0, 'sources_created': 0, 'links_created': 0},
        'locations': {'processed': 0, 'matched': 0, 'sources_created': 0, 'links_created': 0},
        'events': {'processed': 0, 'matched': 0, 'sources_created': 0, 'links_created': 0},
    }


def save_checkpoint(data: Dict):
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# ============ Main Processing ============

def process_persons(limit: int = 0, resume: bool = True):
    """인물 데이터 처리 (배치 쿼리 + 캐싱 최적화)"""
    from app.models import Person

    checkpoint = load_checkpoint() if resume else load_checkpoint()
    stats = checkpoint['persons']
    start_line = stats['processed']

    filepath = EXTRACT_DIR / "persons.jsonl"
    if not filepath.exists():
        print("persons.jsonl not found")
        return

    db = get_db_session()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip already processed lines
            for _ in range(start_line):
                next(f, None)

            processed = 0
            for line in f:
                if limit > 0 and processed >= limit:
                    break

                try:
                    data = json.loads(line.strip())
                    title = data['title']
                    qid = data.get('qid')
                    path = data['path']

                    # DB에서 찾기
                    person, match_type = find_person_in_db(db, qid, title)

                    if person:
                        stats['matched'] += 1

                        # Source 생성
                        source_id = get_or_create_wikipedia_source(db, title, path, qid)
                        stats['sources_created'] += 1

                        # Person-Source 연결
                        link_person_to_source(db, person.id, source_id)

                        # 내부 링크 추출 및 관계 등록 (배치 최적화)
                        html = get_article_html(path)
                        if html:
                            links = extract_internal_links(html, limit=30)
                            link_titles = [link.replace('_', ' ') for link in links]

                            # 배치로 한번에 조회
                            person_matches = batch_find_persons(db, link_titles)
                            event_matches = batch_find_events(db, link_titles)
                            location_matches = batch_find_locations(db, link_titles)

                            for link_title in link_titles:
                                # Person 링크 (상호링크 포함)
                                if link_title in person_matches:
                                    links_added = link_person_to_person(db, person.id, person_matches[link_title], bidirectional=True)
                                    stats['links_created'] += links_added
                                    continue

                                # Event 링크
                                if link_title in event_matches:
                                    link_event_to_person(db, event_matches[link_title], person.id, role="mentioned")
                                    stats['links_created'] += 1
                                    continue

                                # Location 링크
                                if link_title in location_matches:
                                    link_location_to_person(db, location_matches[link_title], person.id)
                                    stats['links_created'] += 1

                        if stats['matched'] % 50 == 0:
                            print(f"  [persons] matched: {stats['matched']}, links: {stats['links_created']}", flush=True)

                except Exception as e:
                    pass

                processed += 1
                stats['processed'] += 1

                # 체크포인트
                if processed % CHECKPOINT_INTERVAL == 0:
                    db.commit()
                    checkpoint['persons'] = stats
                    save_checkpoint(checkpoint)
                    print(f"  [checkpoint] persons: {stats['processed']}", flush=True)

            db.commit()
            checkpoint['persons'] = stats
            save_checkpoint(checkpoint)

    finally:
        db.close()

    print(f"\nPersons completed: {json.dumps(stats, indent=2)}")


def process_events(limit: int = 0, resume: bool = True):
    """이벤트 데이터 처리 (배치 쿼리 + 캐싱 최적화)"""
    checkpoint = load_checkpoint() if resume else load_checkpoint()
    stats = checkpoint['events']
    start_line = stats['processed']

    filepath = EXTRACT_DIR / "events.jsonl"
    if not filepath.exists():
        print("events.jsonl not found")
        return

    db = get_db_session()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for _ in range(start_line):
                next(f, None)

            processed = 0
            for line in f:
                if limit > 0 and processed >= limit:
                    break

                try:
                    data = json.loads(line.strip())
                    title = data['title']
                    qid = data.get('qid')
                    path = data['path']

                    event, match_type = find_event_in_db(db, qid, title)

                    if event:
                        stats['matched'] += 1

                        source_id = get_or_create_wikipedia_source(db, title, path, qid)
                        stats['sources_created'] += 1

                        link_event_to_source(db, event.id, source_id)

                        # 내부 링크 추출 및 관계 등록 (배치 최적화)
                        html = get_article_html(path)
                        if html:
                            links = extract_internal_links(html, limit=30)
                            link_titles = [link.replace('_', ' ') for link in links]

                            # 배치로 한번에 조회
                            person_matches = batch_find_persons(db, link_titles)
                            event_matches = batch_find_events(db, link_titles)
                            location_matches = batch_find_locations(db, link_titles)

                            for link_title in link_titles:
                                # Person 링크
                                if link_title in person_matches:
                                    link_event_to_person(db, event.id, person_matches[link_title])
                                    stats['links_created'] += 1
                                    continue

                                # Event 링크 (상호링크)
                                if link_title in event_matches:
                                    link_event_to_event(db, event.id, event_matches[link_title], rel_type="related_to")
                                    link_event_to_event(db, event_matches[link_title], event.id, rel_type="related_to")
                                    stats['links_created'] += 2
                                    continue

                                # Location 링크
                                if link_title in location_matches:
                                    link_location_to_event(db, location_matches[link_title], event.id)
                                    stats['links_created'] += 1

                        if stats['matched'] % 50 == 0:
                            print(f"  [events] matched: {stats['matched']}, links: {stats['links_created']}", flush=True)

                except Exception as e:
                    pass

                processed += 1
                stats['processed'] += 1

                if processed % CHECKPOINT_INTERVAL == 0:
                    db.commit()
                    checkpoint['events'] = stats
                    save_checkpoint(checkpoint)
                    print(f"  [checkpoint] events: {stats['processed']}", flush=True)

            db.commit()
            checkpoint['events'] = stats
            save_checkpoint(checkpoint)

    finally:
        db.close()

    print(f"\nEvents completed: {json.dumps(stats, indent=2)}")


def process_locations(limit: int = 0, resume: bool = True):
    """장소 데이터 처리 (배치 쿼리 + 캐싱 최적화)"""
    checkpoint = load_checkpoint() if resume else load_checkpoint()
    stats = checkpoint['locations']
    if 'links_created' not in stats:
        stats['links_created'] = 0
    start_line = stats['processed']

    filepath = EXTRACT_DIR / "locations.jsonl"
    if not filepath.exists():
        print("locations.jsonl not found")
        return

    db = get_db_session()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for _ in range(start_line):
                next(f, None)

            processed = 0
            for line in f:
                if limit > 0 and processed >= limit:
                    break

                try:
                    data = json.loads(line.strip())
                    title = data['title']
                    qid = data.get('qid')
                    path = data['path']

                    loc, match_type = find_location_in_db(db, qid, title)

                    if loc:
                        stats['matched'] += 1

                        # Source 생성
                        get_or_create_wikipedia_source(db, title, path, qid)
                        stats['sources_created'] += 1

                        # 내부 링크 추출 및 관계 등록 (배치 최적화)
                        html = get_article_html(path)
                        if html:
                            links = extract_internal_links(html, limit=30)
                            link_titles = [link.replace('_', ' ') for link in links]

                            # 배치로 한번에 조회
                            person_matches = batch_find_persons(db, link_titles)
                            event_matches = batch_find_events(db, link_titles)
                            location_matches = batch_find_locations(db, link_titles)

                            for link_title in link_titles:
                                # Event 링크
                                if link_title in event_matches:
                                    link_location_to_event(db, loc.id, event_matches[link_title])
                                    stats['links_created'] += 1
                                    continue

                                # Person 링크
                                if link_title in person_matches:
                                    link_location_to_person(db, loc.id, person_matches[link_title])
                                    stats['links_created'] += 1
                                    continue

                                # Location 링크 (상호링크)
                                if link_title in location_matches:
                                    link_location_to_location(db, loc.id, location_matches[link_title])
                                    link_location_to_location(db, location_matches[link_title], loc.id)
                                    stats['links_created'] += 2

                        if stats['matched'] % 100 == 0:
                            print(f"  [locations] matched: {stats['matched']}, links: {stats['links_created']}", flush=True)

                except Exception as e:
                    pass

                processed += 1
                stats['processed'] += 1

                if processed % CHECKPOINT_INTERVAL == 0:
                    db.commit()
                    checkpoint['locations'] = stats
                    save_checkpoint(checkpoint)
                    print(f"  [checkpoint] locations: {stats['processed']}", flush=True)

            db.commit()
            checkpoint['locations'] = stats
            save_checkpoint(checkpoint)

    finally:
        db.close()

    print(f"\nLocations completed: {json.dumps(stats, indent=2)}")


def show_stats():
    """현재 통계 표시"""
    checkpoint = load_checkpoint()
    print("=== Linker Stats ===")
    print(json.dumps(checkpoint, indent=2))

    # 파일 라인 수
    for entity_type in ['persons', 'locations', 'events']:
        filepath = EXTRACT_DIR / f"{entity_type}.jsonl"
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                total = sum(1 for _ in f)
            processed = checkpoint.get(entity_type, {}).get('processed', 0)
            print(f"{entity_type}: {processed}/{total} ({processed/total*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Wikipedia-DB Linker")
    parser.add_argument("--type", choices=['persons', 'locations', 'events', 'all'], default='all')
    parser.add_argument("--limit", type=int, default=0, help="0 = no limit")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--fresh", action="store_true", help="Start fresh, ignore checkpoint")
    parser.add_argument("--stats", action="store_true")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    resume = not args.fresh

    print("=== Wikipedia-DB Linker ===", flush=True)
    print(f"Type: {args.type}, Limit: {args.limit or 'unlimited'}, Resume: {resume}", flush=True)
    print("-" * 60, flush=True)

    if args.type in ('persons', 'all'):
        print("\n[Processing persons...]", flush=True)
        process_persons(args.limit, resume)

    if args.type in ('events', 'all'):
        print("\n[Processing events...]", flush=True)
        process_events(args.limit, resume)

    if args.type in ('locations', 'all'):
        print("\n[Processing locations...]", flush=True)
        process_locations(args.limit, resume)

    print("\n" + "=" * 60, flush=True)
    show_stats()


if __name__ == "__main__":
    main()
