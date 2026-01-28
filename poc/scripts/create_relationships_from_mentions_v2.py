#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
본문 언급 기반 관계 생성 (최적화 버전)

content를 단어로 토큰화 → 엔티티 이름 set에서 룩업
O(문서수 × 평균단어수) 복잡도로 빠름

Usage:
    python create_relationships_from_mentions_v2.py --type persons
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_batch


ENRICHED_DIR = Path(__file__).parent.parent / "data" / "wikipedia_enriched"
MIN_NAME_LENGTH = 5


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


def load_entity_names(conn):
    """엔티티 이름 로드 - 이름 → (타입, ID) 매핑"""
    cur = conn.cursor()
    name_to_entity = {}  # name_lower → list of (type, id)

    print("Loading entities...", flush=True)

    # Persons
    cur.execute("SELECT id, name FROM persons WHERE LENGTH(name) >= %s", (MIN_NAME_LENGTH,))
    for eid, name in cur.fetchall():
        if name:
            key = name.lower()
            if key not in name_to_entity:
                name_to_entity[key] = []
            name_to_entity[key].append(('person', eid))
    print(f"  Persons: {len([k for k,v in name_to_entity.items() if any(t=='person' for t,i in v)]):,}", flush=True)

    # Events
    cur.execute("SELECT id, title FROM events WHERE LENGTH(title) >= %s", (MIN_NAME_LENGTH,))
    for eid, title in cur.fetchall():
        if title:
            key = title.lower()
            if key not in name_to_entity:
                name_to_entity[key] = []
            name_to_entity[key].append(('event', eid))
    print(f"  Events: {len([k for k,v in name_to_entity.items() if any(t=='event' for t,i in v)]):,}", flush=True)

    # Locations
    cur.execute("SELECT id, name FROM locations WHERE LENGTH(name) >= %s", (MIN_NAME_LENGTH,))
    for eid, name in cur.fetchall():
        if name:
            key = name.lower()
            if key not in name_to_entity:
                name_to_entity[key] = []
            name_to_entity[key].append(('location', eid))
    print(f"  Locations: {len([k for k,v in name_to_entity.items() if any(t=='location' for t,i in v)]):,}", flush=True)

    print(f"  Total unique names: {len(name_to_entity):,}", flush=True)
    return name_to_entity


def extract_ngrams(text_lower, max_words=5):
    """텍스트에서 1~5 단어 n-gram 추출"""
    words = re.findall(r'\b[a-z][a-z\'\-]+[a-z]\b|\b[a-z]{2,}\b', text_lower)
    ngrams = set()

    for n in range(1, max_words + 1):
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            if len(ngram) >= MIN_NAME_LENGTH:
                ngrams.add(ngram)

    return ngrams


def process_file(entity_type, input_file, name_to_entity, conn):
    """파일 처리"""
    print(f"\n{'='*60}", flush=True)
    print(f"Processing {entity_type.upper()}", flush=True)
    print("="*60, flush=True)

    if not input_file.exists():
        print(f"File not found: {input_file}", flush=True)
        return

    cur = conn.cursor()

    # 기존 관계 로드
    cur.execute("SELECT person_id, related_person_id FROM person_relationships")
    existing_pp = set((min(r[0],r[1]), max(r[0],r[1])) for r in cur.fetchall())

    cur.execute("SELECT event_id, person_id FROM event_persons")
    existing_ep = set(cur.fetchall())

    cur.execute("SELECT event_id, location_id FROM event_locations")
    existing_el = set(cur.fetchall())

    cur.execute("SELECT person_id, location_id FROM person_locations")
    existing_pl = set(cur.fetchall())

    print(f"Existing: PP={len(existing_pp):,} EP={len(existing_ep):,} EL={len(existing_el):,} PL={len(existing_pl):,}", flush=True)

    new_pp, new_ep, new_el, new_pl = [], [], [], []
    total = 0
    start = datetime.now()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            title = record.get('title', '')
            content = record.get('content', '')

            if not content or len(content) < 100:
                continue

            # 소스 엔티티 찾기
            source_key = title.lower()
            source_entities = name_to_entity.get(source_key, [])
            source_info = None
            for etype, eid in source_entities:
                if etype == entity_type[:-1]:  # 'persons' -> 'person'
                    source_info = (etype, eid)
                    break

            if not source_info:
                continue

            source_type, source_id = source_info

            # content에서 n-gram 추출
            content_lower = content.lower()
            ngrams = extract_ngrams(content_lower)

            # 매칭
            for ngram in ngrams:
                if ngram not in name_to_entity:
                    continue
                if ngram == source_key:
                    continue

                for target_type, target_id in name_to_entity[ngram]:
                    if source_type == 'person':
                        if target_type == 'person' and target_id != source_id:
                            pair = (min(source_id, target_id), max(source_id, target_id))
                            if pair not in existing_pp:
                                new_pp.append(pair)
                                existing_pp.add(pair)
                        elif target_type == 'event':
                            pair = (target_id, source_id)
                            if pair not in existing_ep:
                                new_ep.append(pair)
                                existing_ep.add(pair)
                        elif target_type == 'location':
                            pair = (source_id, target_id)
                            if pair not in existing_pl:
                                new_pl.append(pair)
                                existing_pl.add(pair)

                    elif source_type == 'event':
                        if target_type == 'person':
                            pair = (source_id, target_id)
                            if pair not in existing_ep:
                                new_ep.append(pair)
                                existing_ep.add(pair)
                        elif target_type == 'location':
                            pair = (source_id, target_id)
                            if pair not in existing_el:
                                new_el.append(pair)
                                existing_el.add(pair)

            if total % 10000 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                rate = total / elapsed if elapsed > 0 else 0
                print(f"  {total:,} docs | PP:{len(new_pp):,} EP:{len(new_ep):,} EL:{len(new_el):,} PL:{len(new_pl):,} ({rate:.0f}/s)", flush=True)

    print(f"\nTotal: {total:,}", flush=True)
    print(f"New: PP={len(new_pp):,} EP={len(new_ep):,} EL={len(new_el):,} PL={len(new_pl):,}", flush=True)

    # Insert
    if new_pp:
        print(f"Inserting {len(new_pp):,} person_relationships...", flush=True)
        for i in range(0, len(new_pp), 5000):
            batch = [(p1, p2, 'content_mention', 1, 1) for p1, p2 in new_pp[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO person_relationships (person_id, related_person_id, relationship_type, strength, is_bidirectional)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_ep:
        print(f"Inserting {len(new_ep):,} event_persons...", flush=True)
        for i in range(0, len(new_ep), 5000):
            batch = [(eid, pid, 'content_mention') for eid, pid in new_ep[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_el:
        print(f"Inserting {len(new_el):,} event_locations...", flush=True)
        for i in range(0, len(new_el), 5000):
            batch = [(eid, lid, 'content_mention') for eid, lid in new_el[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_locations (event_id, location_id, role)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_pl:
        print(f"Inserting {len(new_pl):,} person_locations...", flush=True)
        for i in range(0, len(new_pl), 5000):
            batch = [(pid, lid, 'content_mention') for pid, lid in new_pl[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO person_locations (person_id, location_id, role)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    print("Done.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=['persons', 'events', 'all'], default='all')
    args = parser.parse_args()

    print("="*60, flush=True)
    print("Content Mention-based Relationships (Optimized)", flush=True)
    print("="*60, flush=True)

    conn = get_db_connection()
    name_to_entity = load_entity_names(conn)

    if args.type in ('persons', 'all'):
        process_file('persons', ENRICHED_DIR / "persons.jsonl", name_to_entity, conn)

    if args.type in ('events', 'all'):
        process_file('events', ENRICHED_DIR / "events.jsonl", name_to_entity, conn)

    conn.close()
    print("\nAll done!", flush=True)


if __name__ == "__main__":
    main()
