#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enriched 데이터를 Sources 테이블에 임포트

1. Sources 테이블에 Wikipedia 소스 생성/업데이트 (content 포함)
2. entity_sources 연결 테이블 업데이트
3. 엔티티의 wikidata_id, wikipedia_url 업데이트

Usage:
    python import_enriched_to_sources.py --type persons
    python import_enriched_to_sources.py --type all
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import json
import argparse
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_batch


ENRICHED_DIR = Path(__file__).parent.parent / "data" / "wikipedia_enriched"


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


def import_persons(conn):
    """Persons enriched 데이터 임포트"""
    print("\n" + "=" * 60, flush=True)
    print("PERSONS 임포트", flush=True)
    print("=" * 60, flush=True)

    cur = conn.cursor()
    input_file = ENRICHED_DIR / "persons.jsonl"

    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    # Person name → id 매핑
    cur.execute("SELECT id, name FROM persons")
    person_by_name = {row[1].lower(): row[0] for row in cur.fetchall() if row[1]}
    print(f"Persons in DB: {len(person_by_name):,}", flush=True)

    # 기존 Wikipedia sources (url 기준)
    cur.execute("SELECT id, url FROM sources WHERE url LIKE 'https://en.wikipedia.org%'")
    source_by_url = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Existing Wikipedia sources: {len(source_by_url):,}", flush=True)

    # 기존 person_sources
    cur.execute("SELECT person_id, source_id FROM person_sources")
    existing_ps = set(cur.fetchall())
    print(f"Existing person_sources: {len(existing_ps):,}", flush=True)

    total = 0
    matched = 0
    sources_created = 0
    sources_updated = 0
    links_created = 0
    wikidata_updated = 0

    start = datetime.now()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            if record.get('_error'):
                continue

            title = record.get('title', '')
            content = record.get('content', '')
            summary = record.get('summary', '')
            wikipedia_url = record.get('wikipedia_url', '')
            qid = record.get('qid')

            if not wikipedia_url or not content:
                continue

            # DB에서 person 찾기
            person_id = person_by_name.get(title.lower())
            if not person_id:
                continue

            matched += 1

            # Source 찾기 또는 생성
            source_id = source_by_url.get(wikipedia_url)

            if source_id:
                # 기존 source 업데이트 (content 추가)
                cur.execute("""
                    UPDATE sources SET content = %s, description = %s, updated_at = NOW()
                    WHERE id = %s AND (content IS NULL OR content = '')
                """, (content, summary, source_id))
                if cur.rowcount > 0:
                    sources_updated += 1
            else:
                # 새 source 생성
                cur.execute("""
                    INSERT INTO sources (name, type, url, description, content, language, created_at, updated_at)
                    VALUES (%s, 'wikipedia', %s, %s, %s, 'en', NOW(), NOW())
                    RETURNING id
                """, (title, wikipedia_url, summary, content))
                source_id = cur.fetchone()[0]
                source_by_url[wikipedia_url] = source_id
                sources_created += 1

            # person_sources 연결
            if (person_id, source_id) not in existing_ps:
                cur.execute("""
                    INSERT INTO person_sources (person_id, source_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (person_id, source_id))
                existing_ps.add((person_id, source_id))
                links_created += 1

            # wikidata_id 업데이트
            if qid:
                cur.execute("""
                    UPDATE persons SET wikidata_id = %s, wikipedia_url = %s
                    WHERE id = %s AND (wikidata_id IS NULL OR wikidata_id = '')
                """, (qid, wikipedia_url, person_id))
                if cur.rowcount > 0:
                    wikidata_updated += 1

            if total % 20000 == 0:
                conn.commit()
                elapsed = (datetime.now() - start).total_seconds()
                print(f"  {total:,} | matched:{matched:,} src+:{sources_created:,} src~:{sources_updated:,} ({total/elapsed:.0f}/s)", flush=True)

    conn.commit()

    print(f"\nTotal: {total:,}", flush=True)
    print(f"Matched: {matched:,}", flush=True)
    print(f"Sources created: {sources_created:,}", flush=True)
    print(f"Sources updated: {sources_updated:,}", flush=True)
    print(f"Links created: {links_created:,}", flush=True)
    print(f"Wikidata updated: {wikidata_updated:,}", flush=True)


def import_events(conn):
    """Events enriched 데이터 임포트"""
    print("\n" + "=" * 60, flush=True)
    print("EVENTS 임포트", flush=True)
    print("=" * 60, flush=True)

    cur = conn.cursor()
    input_file = ENRICHED_DIR / "events.jsonl"

    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    # Event title → id
    cur.execute("SELECT id, title FROM events")
    event_by_title = {row[1].lower(): row[0] for row in cur.fetchall() if row[1]}
    print(f"Events in DB: {len(event_by_title):,}", flush=True)

    # 기존 sources
    cur.execute("SELECT id, url FROM sources WHERE url LIKE 'https://en.wikipedia.org%'")
    source_by_url = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Existing Wikipedia sources: {len(source_by_url):,}", flush=True)

    # 기존 event_sources
    cur.execute("SELECT event_id, source_id FROM event_sources")
    existing_es = set(cur.fetchall())
    print(f"Existing event_sources: {len(existing_es):,}", flush=True)

    total = 0
    matched = 0
    sources_created = 0
    sources_updated = 0
    links_created = 0
    wikidata_updated = 0

    start = datetime.now()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            if record.get('_error'):
                continue

            title = record.get('title', '')
            content = record.get('content', '')
            summary = record.get('summary', '')
            wikipedia_url = record.get('wikipedia_url', '')
            qid = record.get('qid')

            if not wikipedia_url or not content:
                continue

            event_id = event_by_title.get(title.lower())
            if not event_id:
                continue

            matched += 1

            # Source
            source_id = source_by_url.get(wikipedia_url)

            if source_id:
                cur.execute("""
                    UPDATE sources SET content = %s, description = %s, updated_at = NOW()
                    WHERE id = %s AND (content IS NULL OR content = '')
                """, (content, summary, source_id))
                if cur.rowcount > 0:
                    sources_updated += 1
            else:
                cur.execute("""
                    INSERT INTO sources (name, type, url, description, content, language, created_at, updated_at)
                    VALUES (%s, 'wikipedia', %s, %s, %s, 'en', NOW(), NOW())
                    RETURNING id
                """, (title, wikipedia_url, summary, content))
                source_id = cur.fetchone()[0]
                source_by_url[wikipedia_url] = source_id
                sources_created += 1

            # event_sources
            if (event_id, source_id) not in existing_es:
                cur.execute("""
                    INSERT INTO event_sources (event_id, source_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (event_id, source_id))
                existing_es.add((event_id, source_id))
                links_created += 1

            # wikidata_id
            if qid:
                cur.execute("""
                    UPDATE events SET wikidata_id = %s, wikipedia_url = %s
                    WHERE id = %s AND (wikidata_id IS NULL OR wikidata_id = '')
                """, (qid, wikipedia_url, event_id))
                if cur.rowcount > 0:
                    wikidata_updated += 1

            if total % 50000 == 0:
                conn.commit()
                elapsed = (datetime.now() - start).total_seconds()
                print(f"  {total:,} | matched:{matched:,} src+:{sources_created:,} ({total/elapsed:.0f}/s)", flush=True)

    conn.commit()

    print(f"\nTotal: {total:,}", flush=True)
    print(f"Matched: {matched:,}", flush=True)
    print(f"Sources created: {sources_created:,}", flush=True)
    print(f"Sources updated: {sources_updated:,}", flush=True)
    print(f"Links created: {links_created:,}", flush=True)
    print(f"Wikidata updated: {wikidata_updated:,}", flush=True)


def import_locations(conn):
    """Locations enriched 데이터 임포트"""
    print("\n" + "=" * 60, flush=True)
    print("LOCATIONS 임포트", flush=True)
    print("=" * 60, flush=True)

    cur = conn.cursor()
    input_file = ENRICHED_DIR / "locations.jsonl"

    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    # Location name → id
    cur.execute("SELECT id, name FROM locations")
    loc_by_name = {row[1].lower(): row[0] for row in cur.fetchall() if row[1]}
    print(f"Locations in DB: {len(loc_by_name):,}", flush=True)

    # 기존 sources
    cur.execute("SELECT id, url FROM sources WHERE url LIKE 'https://en.wikipedia.org%'")
    source_by_url = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Existing Wikipedia sources: {len(source_by_url):,}", flush=True)

    # 기존 location_sources
    cur.execute("SELECT location_id, source_id FROM location_sources")
    existing_ls = set(cur.fetchall())
    print(f"Existing location_sources: {len(existing_ls):,}", flush=True)

    total = 0
    matched = 0
    sources_created = 0
    sources_updated = 0
    links_created = 0
    wikidata_updated = 0

    start = datetime.now()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                record = json.loads(line)
            except:
                continue

            if record.get('_error'):
                continue

            title = record.get('title', '')
            content = record.get('content', '')
            summary = record.get('summary', '')
            wikipedia_url = record.get('wikipedia_url', '')
            qid = record.get('qid')

            if not wikipedia_url or not content:
                continue

            location_id = loc_by_name.get(title.lower())
            if not location_id:
                continue

            matched += 1

            # Source
            source_id = source_by_url.get(wikipedia_url)

            if source_id:
                cur.execute("""
                    UPDATE sources SET content = %s, description = %s, updated_at = NOW()
                    WHERE id = %s AND (content IS NULL OR content = '')
                """, (content, summary, source_id))
                if cur.rowcount > 0:
                    sources_updated += 1
            else:
                cur.execute("""
                    INSERT INTO sources (name, type, url, description, content, language, created_at, updated_at)
                    VALUES (%s, 'wikipedia', %s, %s, %s, 'en', NOW(), NOW())
                    RETURNING id
                """, (title, wikipedia_url, summary, content))
                source_id = cur.fetchone()[0]
                source_by_url[wikipedia_url] = source_id
                sources_created += 1

            # location_sources
            if (location_id, source_id) not in existing_ls:
                cur.execute("""
                    INSERT INTO location_sources (location_id, source_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (location_id, source_id))
                existing_ls.add((location_id, source_id))
                links_created += 1

            # wikidata_id
            if qid:
                cur.execute("""
                    UPDATE locations SET wikidata_id = %s, wikipedia_url = %s
                    WHERE id = %s AND (wikidata_id IS NULL OR wikidata_id = '')
                """, (qid, wikipedia_url, location_id))
                if cur.rowcount > 0:
                    wikidata_updated += 1

            if total % 100000 == 0:
                conn.commit()
                elapsed = (datetime.now() - start).total_seconds()
                print(f"  {total:,} | matched:{matched:,} src+:{sources_created:,} ({total/elapsed:.0f}/s)", flush=True)

    conn.commit()

    print(f"\nTotal: {total:,}", flush=True)
    print(f"Matched: {matched:,}", flush=True)
    print(f"Sources created: {sources_created:,}", flush=True)
    print(f"Sources updated: {sources_updated:,}", flush=True)
    print(f"Links created: {links_created:,}", flush=True)
    print(f"Wikidata updated: {wikidata_updated:,}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=['persons', 'events', 'locations', 'all'], default='all')
    args = parser.parse_args()

    print("=" * 60, flush=True)
    print("Enriched → Sources 임포트", flush=True)
    print("=" * 60, flush=True)

    conn = get_db_connection()

    if args.type in ('persons', 'all'):
        import_persons(conn)

    if args.type in ('events', 'all'):
        import_events(conn)

    if args.type in ('locations', 'all'):
        import_locations(conn)

    # 최종 현황
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sources")
    print(f"\n최종 sources: {cur.fetchone()[0]:,}", flush=True)

    cur.execute("SELECT COUNT(*) FROM sources WHERE content IS NOT NULL AND content != ''")
    print(f"content 있는 sources: {cur.fetchone()[0]:,}", flush=True)

    conn.close()
    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
