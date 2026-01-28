#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
본문 언급 기반 관계 생성 (빠른 버전)

enriched JSONL의 content에서 다른 엔티티 이름을 검색하여 관계 생성.
Exact match (대소문자 무시), 최소 이름 길이 필터링.

Usage:
    python create_relationships_from_mentions.py --type persons
    python create_relationships_from_mentions.py --type all
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
import multiprocessing as mp
from functools import partial

import psycopg2
from psycopg2.extras import execute_batch


# ============ Config ============

ENRICHED_DIR = Path(__file__).parent.parent / "data" / "wikipedia_enriched"
MIN_NAME_LENGTH = 5  # 너무 짧은 이름 제외 (예: "Li", "Kim")
BATCH_SIZE = 10000


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


# ============ Build Index ============

def load_entity_names(conn):
    """모든 엔티티 이름 로드 → 검색용 인덱스 생성"""
    cur = conn.cursor()

    # Persons
    print("Loading person names...")
    cur.execute("SELECT id, name FROM persons WHERE LENGTH(name) >= %s", (MIN_NAME_LENGTH,))
    person_names = {}  # name_lower → person_id
    for pid, name in cur.fetchall():
        if name:
            person_names[name.lower()] = pid
    print(f"  {len(person_names):,} person names")

    # Events
    print("Loading event titles...")
    cur.execute("SELECT id, title FROM events WHERE LENGTH(title) >= %s", (MIN_NAME_LENGTH,))
    event_names = {}
    for eid, title in cur.fetchall():
        if title:
            event_names[title.lower()] = eid
    print(f"  {len(event_names):,} event titles")

    # Locations
    print("Loading location names...")
    cur.execute("SELECT id, name FROM locations WHERE LENGTH(name) >= %s", (MIN_NAME_LENGTH,))
    location_names = {}
    for lid, name in cur.fetchall():
        if name:
            location_names[name.lower()] = lid
    print(f"  {len(location_names):,} location names")

    return person_names, event_names, location_names


def find_mentions_in_content(content_lower, entity_names, source_entity_id=None):
    """
    content에서 entity 이름 찾기 (빠른 버전)
    Returns: set of entity_ids found
    """
    found = set()
    for name, entity_id in entity_names.items():
        if entity_id == source_entity_id:
            continue  # 자기 자신 제외
        # 단어 경계 체크 (간단 버전)
        if name in content_lower:
            found.add(entity_id)
    return found


def process_persons_mentions(conn, person_names, event_names, location_names):
    """Person 문서에서 다른 엔티티 언급 찾기"""
    print("\n" + "=" * 60)
    print("Processing PERSONS content mentions")
    print("=" * 60)

    input_file = ENRICHED_DIR / "persons.jsonl"
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    cur = conn.cursor()

    # 기존 관계 로드
    cur.execute("SELECT person_id, related_person_id FROM person_relationships")
    existing_pp = set()
    for row in cur.fetchall():
        existing_pp.add((min(row[0], row[1]), max(row[0], row[1])))

    cur.execute("SELECT event_id, person_id FROM event_persons")
    existing_ep = set(cur.fetchall())

    print(f"Existing person_relationships: {len(existing_pp):,}")
    print(f"Existing event_persons: {len(existing_ep):,}")

    new_pp = []
    new_ep = []

    total = 0
    matched = 0

    print("\nScanning persons.jsonl for mentions...")
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

            # 이 person의 DB ID
            source_person_id = person_names.get(title.lower())
            if not source_person_id:
                continue

            content_lower = content.lower()

            # 다른 person 언급 찾기
            for name, target_id in person_names.items():
                if target_id == source_person_id:
                    continue
                if name in content_lower:
                    pair = (min(source_person_id, target_id), max(source_person_id, target_id))
                    if pair not in existing_pp:
                        new_pp.append(pair)
                        existing_pp.add(pair)
                        matched += 1

            # event 언급 찾기
            for name, target_id in event_names.items():
                if name in content_lower:
                    pair = (target_id, source_person_id)
                    if pair not in existing_ep:
                        new_ep.append(pair)
                        existing_ep.add(pair)
                        matched += 1

            if total % 20000 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                rate = total / elapsed if elapsed > 0 else 0
                print(f"  {total:,} scanned, {len(new_pp):,} PP, {len(new_ep):,} EP ({rate:.0f}/s)")

    print(f"\nTotal: {total:,}, New PP: {len(new_pp):,}, New EP: {len(new_ep):,}")

    # Insert
    if new_pp:
        print(f"\nInserting {len(new_pp):,} person_relationships...")
        for i in range(0, len(new_pp), 5000):
            batch = [(p1, p2, 'content_mention', 1, 1) for p1, p2 in new_pp[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO person_relationships (person_id, related_person_id, relationship_type, strength, is_bidirectional)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_ep:
        print(f"Inserting {len(new_ep):,} event_persons...")
        for i in range(0, len(new_ep), 5000):
            batch = [(eid, pid, 'content_mention') for eid, pid in new_ep[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    print("Done.")


def process_events_mentions(conn, person_names, event_names, location_names):
    """Event 문서에서 다른 엔티티 언급 찾기"""
    print("\n" + "=" * 60)
    print("Processing EVENTS content mentions")
    print("=" * 60)

    input_file = ENRICHED_DIR / "events.jsonl"
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    cur = conn.cursor()

    cur.execute("SELECT event_id, person_id FROM event_persons")
    existing_ep = set(cur.fetchall())

    cur.execute("SELECT event_id, location_id FROM event_locations")
    existing_el = set(cur.fetchall())

    print(f"Existing event_persons: {len(existing_ep):,}")
    print(f"Existing event_locations: {len(existing_el):,}")

    new_ep = []
    new_el = []

    total = 0
    start = datetime.now()

    print("\nScanning events.jsonl for mentions...")

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

            source_event_id = event_names.get(title.lower())
            if not source_event_id:
                continue

            content_lower = content.lower()

            # person 언급
            for name, target_id in person_names.items():
                if name in content_lower:
                    pair = (source_event_id, target_id)
                    if pair not in existing_ep:
                        new_ep.append(pair)
                        existing_ep.add(pair)

            # location 언급
            for name, target_id in location_names.items():
                if name in content_lower:
                    pair = (source_event_id, target_id)
                    if pair not in existing_el:
                        new_el.append(pair)
                        existing_el.add(pair)

            if total % 50000 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                rate = total / elapsed if elapsed > 0 else 0
                print(f"  {total:,} scanned, {len(new_ep):,} EP, {len(new_el):,} EL ({rate:.0f}/s)")

    print(f"\nTotal: {total:,}, New EP: {len(new_ep):,}, New EL: {len(new_el):,}")

    if new_ep:
        print(f"\nInserting {len(new_ep):,} event_persons...")
        for i in range(0, len(new_ep), 5000):
            batch = [(eid, pid, 'content_mention') for eid, pid in new_ep[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_el:
        print(f"Inserting {len(new_el):,} event_locations...")
        for i in range(0, len(new_el), 5000):
            batch = [(eid, lid, 'content_mention') for eid, lid in new_el[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_locations (event_id, location_id, role)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Create relationships from content mentions")
    parser.add_argument("--type", choices=['persons', 'events', 'all'], default='all')

    args = parser.parse_args()

    print("=" * 60)
    print("Content Mention-based Relationship Generation")
    print(f"Min name length: {MIN_NAME_LENGTH}")
    print("=" * 60)

    conn = get_db_connection()
    person_names, event_names, location_names = load_entity_names(conn)

    if args.type in ('persons', 'all'):
        process_persons_mentions(conn, person_names, event_names, location_names)

    if args.type in ('events', 'all'):
        process_events_mentions(conn, person_names, event_names, location_names)

    conn.close()
    print("\n" + "=" * 60)
    print("All done!")


if __name__ == "__main__":
    main()
