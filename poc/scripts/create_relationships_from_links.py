#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Wikipedia 하이퍼링크 기반 관계 생성

enriched JSONL의 links 필드를 사용하여 엔티티 간 관계를 생성합니다.

Usage:
    python create_relationships_from_links.py --type persons
    python create_relationships_from_links.py --type events
    python create_relationships_from_links.py --type all
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_batch


# ============ Config ============

ENRICHED_DIR = Path(__file__).parent.parent / "data" / "wikipedia_enriched"


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


# ============ Build Index ============

def build_title_to_entity_maps(conn):
    """
    Wikipedia 타이틀 → DB 엔티티 ID 매핑 생성
    """
    print("Building title → entity maps...")
    cur = conn.cursor()

    # Person: name → id
    print("  Loading persons...")
    cur.execute("SELECT id, name FROM persons")
    person_by_name = {}
    for row in cur.fetchall():
        pid, name = row
        if name:
            person_by_name[name.lower()] = pid
    print(f"    {len(person_by_name):,} person names indexed")

    # Event: title → id
    print("  Loading events...")
    cur.execute("SELECT id, title FROM events")
    event_by_name = {}
    for row in cur.fetchall():
        eid, title = row
        if title:
            event_by_name[title.lower()] = eid
    print(f"    {len(event_by_name):,} event names indexed")

    # Location: name → id
    print("  Loading locations...")
    cur.execute("SELECT id, name FROM locations")
    location_by_name = {}
    for row in cur.fetchall():
        lid, name = row
        if name:
            location_by_name[name.lower()] = lid
    print(f"    {len(location_by_name):,} location names indexed")

    return person_by_name, event_by_name, location_by_name


def build_qid_to_entity_maps(conn):
    """
    Wikidata QID → DB 엔티티 ID 매핑 생성
    """
    print("Building QID → entity maps...")
    cur = conn.cursor()

    # Person: wikidata_id → id
    print("  Loading persons with wikidata_id...")
    cur.execute("SELECT id, wikidata_id FROM persons WHERE wikidata_id IS NOT NULL")
    person_by_qid = {row[1]: row[0] for row in cur.fetchall()}
    print(f"    {len(person_by_qid):,} persons with QID")

    # Event: wikidata_id → id (컬럼 있으면)
    event_by_qid = {}
    try:
        cur.execute("SELECT id, wikidata_id FROM events WHERE wikidata_id IS NOT NULL")
        event_by_qid = {row[1]: row[0] for row in cur.fetchall()}
        print(f"    {len(event_by_qid):,} events with QID")
    except:
        print("    events.wikidata_id 컬럼 없음")

    # Location: wikidata_id → id (컬럼 있으면)
    location_by_qid = {}
    try:
        cur.execute("SELECT id, wikidata_id FROM locations WHERE wikidata_id IS NOT NULL")
        location_by_qid = {row[1]: row[0] for row in cur.fetchall()}
        print(f"    {len(location_by_qid):,} locations with QID")
    except:
        print("    locations.wikidata_id 컬럼 없음")

    return person_by_qid, event_by_qid, location_by_qid


# ============ Process Persons ============

def process_persons_links(conn, person_by_name, event_by_name, location_by_name):
    """
    Person 문서의 링크에서 관계 추출

    - Person → Person = person_relationships
    - Person → Event = event_persons
    - Person → Location = person_locations
    """
    print("\n" + "=" * 60)
    print("Processing PERSONS links")
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
    print(f"Existing person_relationships: {len(existing_pp):,}")

    cur.execute("SELECT event_id, person_id FROM event_persons")
    existing_ep = set(cur.fetchall())
    print(f"Existing event_persons: {len(existing_ep):,}")

    # 새 관계 수집
    new_pp = []  # (person1_id, person2_id)
    new_ep = []  # (event_id, person_id)

    total = 0
    matched_links = 0

    print("\nScanning persons.jsonl...")
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            title = record.get('title', '')
            links = record.get('links', [])

            if not links:
                continue

            # 이 person의 DB ID 찾기
            source_person_id = person_by_name.get(title.lower())
            if not source_person_id:
                continue

            for link in links:
                link_lower = link.lower()
                matched_links += 1

                # Person 링크?
                target_person_id = person_by_name.get(link_lower)
                if target_person_id and target_person_id != source_person_id:
                    pair = (min(source_person_id, target_person_id), max(source_person_id, target_person_id))
                    if pair not in existing_pp:
                        new_pp.append(pair)
                        existing_pp.add(pair)
                    continue

                # Event 링크?
                target_event_id = event_by_name.get(link_lower)
                if target_event_id:
                    pair = (target_event_id, source_person_id)
                    if pair not in existing_ep:
                        new_ep.append(pair)
                        existing_ep.add(pair)
                    continue

            if total % 50000 == 0:
                print(f"  {total:,} records scanned, {len(new_pp):,} PP, {len(new_ep):,} EP")

    print(f"\nTotal records: {total:,}")
    print(f"Links checked: {matched_links:,}")
    print(f"New person_relationships: {len(new_pp):,}")
    print(f"New event_persons: {len(new_ep):,}")

    # Insert person_relationships
    if new_pp:
        print(f"\nInserting {len(new_pp):,} person_relationships...")
        batch_size = 5000
        for i in range(0, len(new_pp), batch_size):
            batch = [(p1, p2, 'wikipedia_link', 1, 1) for p1, p2 in new_pp[i:i+batch_size]]
            execute_batch(cur, """
                INSERT INTO person_relationships (person_id, related_person_id, relationship_type, strength, is_bidirectional)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()
            if (i + batch_size) % 50000 == 0:
                print(f"  {min(i+batch_size, len(new_pp)):,} / {len(new_pp):,}")

    # Insert event_persons
    if new_ep:
        print(f"\nInserting {len(new_ep):,} event_persons...")
        batch_size = 5000
        for i in range(0, len(new_ep), batch_size):
            batch = [(eid, pid, 'wikipedia_link') for eid, pid in new_ep[i:i+batch_size]]
            execute_batch(cur, """
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    conn.commit()
    print("Done processing persons links.")


def process_events_links(conn, person_by_name, event_by_name, location_by_name):
    """
    Event 문서의 링크에서 관계 추출

    - Event → Person = event_persons
    - Event → Location = event_locations
    """
    print("\n" + "=" * 60)
    print("Processing EVENTS links")
    print("=" * 60)

    input_file = ENRICHED_DIR / "events.jsonl"
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    cur = conn.cursor()

    # 기존 관계 로드
    cur.execute("SELECT event_id, person_id FROM event_persons")
    existing_ep = set(cur.fetchall())
    print(f"Existing event_persons: {len(existing_ep):,}")

    cur.execute("SELECT event_id, location_id FROM event_locations")
    existing_el = set(cur.fetchall())
    print(f"Existing event_locations: {len(existing_el):,}")

    new_ep = []
    new_el = []

    total = 0

    print("\nScanning events.jsonl...")
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            title = record.get('title', '')
            links = record.get('links', [])

            if not links:
                continue

            # 이 event의 DB ID 찾기
            source_event_id = event_by_name.get(title.lower())
            if not source_event_id:
                continue

            for link in links:
                link_lower = link.lower()

                # Person 링크?
                target_person_id = person_by_name.get(link_lower)
                if target_person_id:
                    pair = (source_event_id, target_person_id)
                    if pair not in existing_ep:
                        new_ep.append(pair)
                        existing_ep.add(pair)
                    continue

                # Location 링크?
                target_location_id = location_by_name.get(link_lower)
                if target_location_id:
                    pair = (source_event_id, target_location_id)
                    if pair not in existing_el:
                        new_el.append(pair)
                        existing_el.add(pair)
                    continue

            if total % 50000 == 0:
                print(f"  {total:,} records scanned, {len(new_ep):,} EP, {len(new_el):,} EL")

    print(f"\nTotal records: {total:,}")
    print(f"New event_persons: {len(new_ep):,}")
    print(f"New event_locations: {len(new_el):,}")

    # Insert
    if new_ep:
        print(f"\nInserting {len(new_ep):,} event_persons...")
        batch_size = 5000
        for i in range(0, len(new_ep), batch_size):
            batch = [(eid, pid, 'wikipedia_link') for eid, pid in new_ep[i:i+batch_size]]
            execute_batch(cur, """
                INSERT INTO event_persons (event_id, person_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_el:
        print(f"\nInserting {len(new_el):,} event_locations...")
        batch_size = 5000
        for i in range(0, len(new_el), batch_size):
            batch = [(eid, lid, 'wikipedia_link') for eid, lid in new_el[i:i+batch_size]]
            execute_batch(cur, """
                INSERT INTO event_locations (event_id, location_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    conn.commit()
    print("Done processing events links.")


def process_locations_links(conn, person_by_name, event_by_name, location_by_name):
    """
    Location 문서의 링크에서 관계 추출

    - Location → Person = person_locations
    - Location → Event = event_locations
    """
    print("\n" + "=" * 60)
    print("Processing LOCATIONS links")
    print("=" * 60)

    input_file = ENRICHED_DIR / "locations.jsonl"
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    cur = conn.cursor()

    # 기존 관계 로드
    cur.execute("SELECT person_id, location_id FROM person_locations")
    existing_pl = set(cur.fetchall())
    print(f"Existing person_locations: {len(existing_pl):,}")

    cur.execute("SELECT event_id, location_id FROM event_locations")
    existing_el = set(cur.fetchall())
    print(f"Existing event_locations: {len(existing_el):,}")

    new_pl = []
    new_el = []

    total = 0

    print("\nScanning locations.jsonl...")
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            title = record.get('title', '')
            links = record.get('links', [])

            if not links:
                continue

            # 이 location의 DB ID 찾기
            source_location_id = location_by_name.get(title.lower())
            if not source_location_id:
                continue

            for link in links:
                link_lower = link.lower()

                # Person 링크?
                target_person_id = person_by_name.get(link_lower)
                if target_person_id:
                    pair = (target_person_id, source_location_id)
                    if pair not in existing_pl:
                        new_pl.append(pair)
                        existing_pl.add(pair)
                    continue

                # Event 링크?
                target_event_id = event_by_name.get(link_lower)
                if target_event_id:
                    pair = (target_event_id, source_location_id)
                    if pair not in existing_el:
                        new_el.append(pair)
                        existing_el.add(pair)
                    continue

            if total % 100000 == 0:
                print(f"  {total:,} records scanned, {len(new_pl):,} PL, {len(new_el):,} EL")

    print(f"\nTotal records: {total:,}")
    print(f"New person_locations: {len(new_pl):,}")
    print(f"New event_locations: {len(new_el):,}")

    # Insert
    if new_pl:
        print(f"\nInserting {len(new_pl):,} person_locations...")
        batch_size = 5000
        for i in range(0, len(new_pl), batch_size):
            batch = [(pid, lid, 'wikipedia_link') for pid, lid in new_pl[i:i+batch_size]]
            execute_batch(cur, """
                INSERT INTO person_locations (person_id, location_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    if new_el:
        print(f"\nInserting {len(new_el):,} event_locations...")
        batch_size = 5000
        for i in range(0, len(new_el), batch_size):
            batch = [(eid, lid, 'wikipedia_link') for eid, lid in new_el[i:i+batch_size]]
            execute_batch(cur, """
                INSERT INTO event_locations (event_id, location_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    conn.commit()
    print("Done processing locations links.")


# ============ Main ============

def main():
    parser = argparse.ArgumentParser(description="Create relationships from Wikipedia links")
    parser.add_argument("--type", choices=['persons', 'events', 'locations', 'all'], default='all')
    parser.add_argument("--dry-run", action="store_true", help="Count only, no insert")

    args = parser.parse_args()

    print("=" * 60)
    print("Wikipedia Link-based Relationship Generation")
    print(f"Type: {args.type}")
    print("=" * 60)

    conn = get_db_connection()

    # Build maps
    person_by_name, event_by_name, location_by_name = build_title_to_entity_maps(conn)

    if args.type == 'all':
        process_persons_links(conn, person_by_name, event_by_name, location_by_name)
        process_events_links(conn, person_by_name, event_by_name, location_by_name)
        process_locations_links(conn, person_by_name, event_by_name, location_by_name)
    elif args.type == 'persons':
        process_persons_links(conn, person_by_name, event_by_name, location_by_name)
    elif args.type == 'events':
        process_events_links(conn, person_by_name, event_by_name, location_by_name)
    elif args.type == 'locations':
        process_locations_links(conn, person_by_name, event_by_name, location_by_name)

    conn.close()
    print("\n" + "=" * 60)
    print("All done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
