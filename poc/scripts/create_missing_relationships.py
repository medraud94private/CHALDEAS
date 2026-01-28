#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
누락된 관계 생성: Event-Event, Location-Location

Usage:
    python create_missing_relationships.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import json
import re
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_batch


ENRICHED_DIR = Path(__file__).parent.parent / "data" / "wikipedia_enriched"
MIN_NAME_LENGTH = 5


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


def extract_ngrams(text_lower, max_words=6):
    words = re.findall(r'\b[a-z][a-z\'\-]+[a-z]\b|\b[a-z]{2,}\b', text_lower)
    ngrams = set()
    for n in range(1, max_words + 1):
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            if len(ngram) >= MIN_NAME_LENGTH:
                ngrams.add(ngram)
    return ngrams


def process_event_event(conn):
    """Event-Event 관계 생성"""
    print("\n" + "=" * 60, flush=True)
    print("EVENT-EVENT 관계 생성", flush=True)
    print("=" * 60, flush=True)

    cur = conn.cursor()

    # Event titles
    cur.execute("SELECT id, title FROM events WHERE LENGTH(title) >= %s", (MIN_NAME_LENGTH,))
    event_by_title = {row[1].lower(): row[0] for row in cur.fetchall() if row[1]}
    print(f"Events: {len(event_by_title):,}", flush=True)

    # 기존 관계
    cur.execute("SELECT from_event_id, to_event_id FROM event_relationships")
    existing = set((min(r[0],r[1]), max(r[0],r[1])) for r in cur.fetchall())
    print(f"Existing: {len(existing):,}", flush=True)

    input_file = ENRICHED_DIR / "events.jsonl"
    new_rels = []
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
            links = record.get('links', [])
            content = record.get('content', '')

            source_id = event_by_title.get(title.lower())
            if not source_id:
                continue

            found = set()

            # 링크
            for link in links:
                tid = event_by_title.get(link.lower())
                if tid and tid != source_id:
                    found.add(tid)

            # 본문
            if content:
                for ngram in extract_ngrams(content.lower()):
                    tid = event_by_title.get(ngram)
                    if tid and tid != source_id:
                        found.add(tid)

            for tid in found:
                pair = (min(source_id, tid), max(source_id, tid))
                if pair not in existing:
                    new_rels.append((source_id, tid))
                    existing.add(pair)

            if total % 50000 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                print(f"  {total:,} | {len(new_rels):,} new ({total/elapsed:.0f}/s)", flush=True)

    print(f"New Event-Event: {len(new_rels):,}", flush=True)

    if new_rels:
        print("Inserting...", flush=True)
        for i in range(0, len(new_rels), 5000):
            batch = [(f, t, 'wikipedia_mention', 1.0) for f, t in new_rels[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_relationships (from_event_id, to_event_id, relationship_type, strength)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    cur.execute("SELECT COUNT(*) FROM event_relationships")
    print(f"Final event_relationships: {cur.fetchone()[0]:,}", flush=True)


def process_location_location(conn):
    """Location-Location 관계 생성"""
    print("\n" + "=" * 60, flush=True)
    print("LOCATION-LOCATION 관계 생성", flush=True)
    print("=" * 60, flush=True)

    cur = conn.cursor()

    # location_relationships 테이블 확인/생성
    cur.execute("""
        CREATE TABLE IF NOT EXISTS location_relationships (
            id SERIAL PRIMARY KEY,
            location_id INTEGER REFERENCES locations(id),
            related_location_id INTEGER REFERENCES locations(id),
            relationship_type VARCHAR(100),
            strength REAL DEFAULT 1.0,
            UNIQUE(location_id, related_location_id)
        )
    """)
    conn.commit()

    # Location names
    cur.execute("SELECT id, name FROM locations WHERE LENGTH(name) >= %s", (MIN_NAME_LENGTH,))
    loc_by_name = {row[1].lower(): row[0] for row in cur.fetchall() if row[1]}
    print(f"Locations: {len(loc_by_name):,}", flush=True)

    # 기존 관계
    cur.execute("SELECT location_id, related_location_id FROM location_relationships")
    existing = set((min(r[0],r[1]), max(r[0],r[1])) for r in cur.fetchall())
    print(f"Existing: {len(existing):,}", flush=True)

    input_file = ENRICHED_DIR / "locations.jsonl"
    new_rels = []
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
            links = record.get('links', [])
            content = record.get('content', '')

            source_id = loc_by_name.get(title.lower())
            if not source_id:
                continue

            found = set()

            # 링크
            for link in links:
                tid = loc_by_name.get(link.lower())
                if tid and tid != source_id:
                    found.add(tid)

            # 본문
            if content:
                for ngram in extract_ngrams(content.lower()):
                    tid = loc_by_name.get(ngram)
                    if tid and tid != source_id:
                        found.add(tid)

            for tid in found:
                pair = (min(source_id, tid), max(source_id, tid))
                if pair not in existing:
                    new_rels.append((source_id, tid))
                    existing.add(pair)

            if total % 100000 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                print(f"  {total:,} | {len(new_rels):,} new ({total/elapsed:.0f}/s)", flush=True)

    print(f"New Location-Location: {len(new_rels):,}", flush=True)

    if new_rels:
        print("Inserting...", flush=True)
        for i in range(0, len(new_rels), 5000):
            batch = [(f, t, 'wikipedia_mention', 1.0) for f, t in new_rels[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO location_relationships (location_id, related_location_id, relationship_type, strength)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()

    cur.execute("SELECT COUNT(*) FROM location_relationships")
    print(f"Final location_relationships: {cur.fetchone()[0]:,}", flush=True)


def main():
    print("=" * 60, flush=True)
    print("누락된 관계 생성: Event-Event, Location-Location", flush=True)
    print("=" * 60, flush=True)

    conn = get_db_connection()

    process_event_event(conn)
    process_location_location(conn)

    conn.close()
    print("\nAll done!", flush=True)


if __name__ == "__main__":
    main()
