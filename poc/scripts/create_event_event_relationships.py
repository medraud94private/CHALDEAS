#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Event-Event 관계 생성

enriched events.jsonl의 links와 content에서 다른 Event 언급 찾아 관계 생성

Usage:
    python create_event_event_relationships.py
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
    """텍스트에서 n-gram 추출"""
    words = re.findall(r'\b[a-z][a-z\'\-]+[a-z]\b|\b[a-z]{2,}\b', text_lower)
    ngrams = set()
    for n in range(1, max_words + 1):
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            if len(ngram) >= MIN_NAME_LENGTH:
                ngrams.add(ngram)
    return ngrams


def main():
    print("=" * 60, flush=True)
    print("Event-Event 관계 생성", flush=True)
    print("=" * 60, flush=True)

    conn = get_db_connection()
    cur = conn.cursor()

    # Event titles 로드
    print("\nLoading event titles...", flush=True)
    cur.execute("SELECT id, title FROM events WHERE LENGTH(title) >= %s", (MIN_NAME_LENGTH,))
    event_by_title = {}
    for eid, title in cur.fetchall():
        if title:
            event_by_title[title.lower()] = eid
    print(f"  {len(event_by_title):,} events loaded", flush=True)

    # 기존 관계 로드
    cur.execute("SELECT from_event_id, to_event_id FROM event_relationships")
    existing = set()
    for row in cur.fetchall():
        existing.add((min(row[0], row[1]), max(row[0], row[1])))
    print(f"  Existing event_relationships: {len(existing):,}", flush=True)

    input_file = ENRICHED_DIR / "events.jsonl"
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    new_rels = []
    total = 0
    start = datetime.now()

    print("\nScanning events.jsonl...", flush=True)

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

            found_events = set()

            # 1. 링크에서 찾기
            for link in links:
                target_id = event_by_title.get(link.lower())
                if target_id and target_id != source_id:
                    found_events.add(target_id)

            # 2. 본문에서 찾기
            if content:
                ngrams = extract_ngrams(content.lower())
                for ngram in ngrams:
                    target_id = event_by_title.get(ngram)
                    if target_id and target_id != source_id:
                        found_events.add(target_id)

            # 새 관계 추가
            for target_id in found_events:
                pair = (min(source_id, target_id), max(source_id, target_id))
                if pair not in existing:
                    new_rels.append((source_id, target_id))
                    existing.add(pair)

            if total % 50000 == 0:
                elapsed = (datetime.now() - start).total_seconds()
                rate = total / elapsed if elapsed > 0 else 0
                print(f"  {total:,} docs | {len(new_rels):,} new rels ({rate:.0f}/s)", flush=True)

    print(f"\nTotal: {total:,}, New relationships: {len(new_rels):,}", flush=True)

    if new_rels:
        print(f"\nInserting {len(new_rels):,} event_relationships...", flush=True)
        for i in range(0, len(new_rels), 5000):
            batch = [(fid, tid, 'wikipedia_mention', 1.0) for fid, tid in new_rels[i:i+5000]]
            execute_batch(cur, """
                INSERT INTO event_relationships (from_event_id, to_event_id, relationship_type, strength)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, batch)
            conn.commit()
            print(f"  {min(i+5000, len(new_rels)):,} / {len(new_rels):,}", flush=True)

    cur.execute("SELECT COUNT(*) FROM event_relationships")
    final = cur.fetchone()[0]
    print(f"\nFinal event_relationships: {final:,}", flush=True)

    conn.close()
    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
