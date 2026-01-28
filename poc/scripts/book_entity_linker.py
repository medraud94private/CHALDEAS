#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Book Entity Linker - 책/문서에서 기존 DB 엔티티 매칭 (최적화 버전)

Usage:
    python book_entity_linker.py --analyze
"""

import sys
import re
import argparse
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'chaldeas',
    'user': 'chaldeas',
    'password': 'chaldeas_dev',
    'port': 5432
}


COMMON_WORDS = {
    # 일반 단어
    'the', 'and', 'that', 'this', 'with', 'from', 'have', 'been', 'were', 'was',
    'which', 'their', 'there', 'would', 'could', 'should', 'about', 'after',
    'before', 'between', 'through', 'during', 'without', 'against', 'under',
    # 시간/달
    'january', 'february', 'march', 'april', 'june', 'july', 'august',
    'september', 'october', 'november', 'december', 'early', 'late',
    # 일반 명사
    'general', 'north', 'south', 'east', 'west', 'death', 'large', 'small',
    'world', 'soldiers', 'public', 'victory', 'times', 'house', 'english',
    'himself', 'herself', 'order', 'orders', 'work', 'works', 'name',
    'british', 'french', 'german', 'second', 'third', 'first', 'close',
    'little', 'great', 'ancient', 'modern', 'roman', 'greek',
}


def get_db_entities(conn, min_name_len=5, limit=5000):
    """DB에서 연결 많은 엔티티 이름 가져오기 (상위만)"""
    cur = conn.cursor()

    entities = {
        'persons': {},
        'locations': {},
    }

    # Persons - 연결 많은 순, 이름에 공백 포함하거나 대문자로 시작하는 것만
    cur.execute("""
        SELECT id, name, connection_count FROM persons
        WHERE connection_count > 5 AND LENGTH(name) >= %s
        AND (name LIKE '%% %%' OR name ~ '^[A-Z].*[a-z]')
        ORDER BY connection_count DESC
        LIMIT %s
    """, (min_name_len, limit))
    for row in cur.fetchall():
        name_lower = row[1].lower()
        if name_lower not in COMMON_WORDS and not name_lower.isdigit():
            entities['persons'][name_lower] = {'id': row[0], 'name': row[1], 'conn': row[2]}

    # Locations - 연결 많은 순
    cur.execute("""
        SELECT id, name, connection_count FROM locations
        WHERE connection_count > 0 AND LENGTH(name) >= %s
        ORDER BY connection_count DESC
        LIMIT %s
    """, (min_name_len, limit))
    for row in cur.fetchall():
        name_lower = row[1].lower()
        entities['locations'][name_lower] = {'id': row[0], 'name': row[1], 'conn': row[2]}

    print(f"Loaded {len(entities['persons']):,} persons, {len(entities['locations']):,} locations")
    return entities


def chunk_text(text: str, chunk_size: int = 1500) -> list[dict]:
    """텍스트 청킹 (문단 기준)"""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) < chunk_size:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks


def find_entities_fast(text: str, entities: dict) -> dict:
    """빠른 엔티티 매칭 (set 기반)"""
    found = {'persons': [], 'locations': []}
    words = set(re.findall(r'\b[a-zA-Z]{4,}\b', text.lower()))

    for entity_type in ['persons', 'locations']:
        for name_lower, info in entities[entity_type].items():
            # 단일 단어 이름만 빠른 매칭
            name_parts = name_lower.split()
            if len(name_parts) == 1:
                if name_lower in words:
                    found[entity_type].append(info)
            else:
                # 복합 이름은 정규식
                if all(p in text.lower() for p in name_parts[:2]):
                    pattern = r'\b' + re.escape(name_lower) + r'\b'
                    if re.search(pattern, text.lower()):
                        found[entity_type].append(info)

    return found


def analyze_book(text: str, entities: dict) -> dict:
    """책 분석"""
    chunks = chunk_text(text)
    print(f"Total chunks: {len(chunks)}")

    all_persons = {}
    all_locations = {}
    co_occurrences = defaultdict(int)

    for i, chunk in enumerate(chunks):
        if i % 10 == 0:
            print(f"  Processing chunk {i+1}/{len(chunks)}...")

        found = find_entities_fast(chunk, entities)

        # 발견된 엔티티 기록
        for p in found['persons']:
            all_persons[p['id']] = p
        for l in found['locations']:
            all_locations[l['id']] = l

        # 동시 출현
        chunk_entities = [(p['id'], 'P', p['name']) for p in found['persons']]
        chunk_entities += [(l['id'], 'L', l['name']) for l in found['locations']]

        for i, e1 in enumerate(chunk_entities):
            for e2 in chunk_entities[i+1:]:
                if e1[0] != e2[0]:  # 다른 엔티티만
                    key = tuple(sorted([(e1[0], e1[1]), (e2[0], e2[1])]))
                    co_occurrences[key] += 1

    return {
        'persons': all_persons,
        'locations': all_locations,
        'co_occurrences': co_occurrences,
        'chunks': len(chunks)
    }


def get_book_from_wikisource(path: str) -> str:
    """Wikisource에서 책 가져오기"""
    from kiwix_reader import get_archive, html_to_text

    archive = get_archive('wikisource')
    entry = archive.get_entry_by_path(path)
    item = entry.get_item()
    html = bytes(item.content).decode('utf-8', errors='ignore')
    return html_to_text(html)


def link_entities_to_source(conn, source_id: int, persons: dict, locations: dict, dry_run: bool = True):
    """엔티티에 소스 연결 (person_sources, location_sources)"""
    cur = conn.cursor()
    linked = 0

    for p_id, p_info in persons.items():
        if dry_run:
            print(f"  [DRY] person_sources: person {p_id} ({p_info['name']}) <- source {source_id}")
        else:
            cur.execute("""
                INSERT INTO person_sources (person_id, source_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (p_id, source_id))
            linked += cur.rowcount

    for l_id, l_info in locations.items():
        if dry_run:
            print(f"  [DRY] location_sources: location {l_id} ({l_info['name']}) <- source {source_id}")
        else:
            cur.execute("""
                INSERT INTO location_sources (location_id, source_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (l_id, source_id))
            linked += cur.rowcount

    if not dry_run:
        conn.commit()

    return linked


def create_source(conn, source_name: str, content: str) -> int:
    """소스 생성/조회"""
    cur = conn.cursor()
    cur.execute("SELECT id FROM sources WHERE title = %s", (source_name,))
    result = cur.fetchone()
    if result:
        return result[0]

    cur.execute("""
        INSERT INTO sources (name, title, type, url, archive_type, content, created_at, updated_at)
        VALUES (%s, %s, 'book', %s, 'wikisource', %s, NOW(), NOW())
        RETURNING id
    """, (source_name, source_name, f'https://en.wikisource.org/wiki/{source_name}', content))
    source_id = cur.fetchone()[0]
    conn.commit()
    return source_id


def create_relationships(conn, co_occurrences: dict, source_id: int, dry_run: bool = True):
    """동시 출현 기반 관계 생성"""
    cur = conn.cursor()
    created = 0

    for key, count in co_occurrences.items():
        if count < 2:  # 최소 2번 동시 출현
            continue

        (e1_id, e1_type), (e2_id, e2_type) = key

        # Person-Person 관계
        if e1_type == 'P' and e2_type == 'P':
            strength_boost = min(count * 2, 20)  # 최대 20점 부스트

            if dry_run:
                print(f"  [DRY] person_relationships: {e1_id} <-> {e2_id} (+{strength_boost})")
            else:
                # 기존 관계 업데이트 또는 신규 생성
                cur.execute("""
                    INSERT INTO person_relationships (person_id, related_person_id, relationship_type, strength, source_id)
                    VALUES (%s, %s, 'co_mentioned', %s, %s)
                    ON CONFLICT (person_id, related_person_id)
                    DO UPDATE SET strength = person_relationships.strength + EXCLUDED.strength
                """, (e1_id, e2_id, strength_boost, source_id))
                created += cur.rowcount

        # Person-Location 관계
        elif (e1_type == 'P' and e2_type == 'L') or (e1_type == 'L' and e2_type == 'P'):
            person_id = e1_id if e1_type == 'P' else e2_id
            location_id = e1_id if e1_type == 'L' else e2_id

            if dry_run:
                print(f"  [DRY] person_locations: person {person_id} <-> location {location_id}")
            else:
                cur.execute("""
                    INSERT INTO person_locations (person_id, location_id, relationship_type, source_id)
                    VALUES (%s, %s, 'mentioned_with', %s)
                    ON CONFLICT DO NOTHING
                """, (person_id, location_id, source_id))
                created += cur.rowcount

    if not dry_run:
        conn.commit()
        print(f"Created/updated {created} relationships")

    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='1911_Encyclopædia_Britannica/Julius_Caesar')
    parser.add_argument('--analyze', action='store_true')
    parser.add_argument('--create-relations', action='store_true', help='Create relationships from co-occurrences')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created')
    args = parser.parse_args()

    print("=" * 60)
    print("Book Entity Linker")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    entities = get_db_entities(conn, min_name_len=4, limit=3000)

    print(f"\nFetching: {args.path}")
    text = get_book_from_wikisource(args.path)
    print(f"Text length: {len(text):,} chars")

    print("\nAnalyzing...")
    result = analyze_book(text, entities)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\nPersons found: {len(result['persons'])}")
    sorted_persons = sorted(result['persons'].values(), key=lambda x: -x['conn'])[:25]
    for p in sorted_persons:
        print(f"  - {p['name']} (connections: {p['conn']})")

    print(f"\nLocations found: {len(result['locations'])}")
    sorted_locs = sorted(result['locations'].values(), key=lambda x: -x['conn'])[:15]
    for l in sorted_locs:
        print(f"  - {l['name']} (connections: {l['conn']})")

    print(f"\nTop co-occurrences:")
    sorted_co = sorted(result['co_occurrences'].items(), key=lambda x: -x[1])[:20]
    for key, count in sorted_co:
        e1_id, e1_type = key[0]
        e2_id, e2_type = key[1]
        e1_name = result['persons'].get(e1_id, result['locations'].get(e1_id, {})).get('name', '?')
        e2_name = result['persons'].get(e2_id, result['locations'].get(e2_id, {})).get('name', '?')
        print(f"  {e1_name} <-> {e2_name}: {count} chunks")

    # 관계 생성
    if args.create_relations:
        print("\n" + "=" * 60)
        print("Creating relationships...")
        print("=" * 60)
        create_relationships(conn, result['co_occurrences'], args.path, dry_run=args.dry_run)

    conn.close()


if __name__ == '__main__':
    main()
