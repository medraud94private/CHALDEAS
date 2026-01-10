#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NER 이벤트-소스 연결 스크립트

NER aggregated events의 source_docs를 text_mentions 테이블에 연결합니다.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='chaldeas',
        user='chaldeas',
        password='chaldeas_dev',
        port=5432
    )


def load_ner_events():
    """NER aggregated events 로드."""
    path = Path(__file__).parent.parent / "data" / "integrated_ner_full" / "aggregated" / "events.json"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_source_index(conn):
    """document_id -> source_id 인덱스 생성."""
    cur = conn.cursor()
    cur.execute('SELECT id, document_id FROM sources WHERE document_id IS NOT NULL')
    index = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Source index built: {len(index):,} entries")
    return index


def build_event_slug_index(conn):
    """NER event slug -> event_id 인덱스 생성."""
    cur = conn.cursor()
    cur.execute("SELECT id, slug FROM events WHERE slug LIKE 'ner-%%'")
    index = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Event slug index built: {len(index):,} entries")
    return index


def make_slug(name, year, index):
    """이벤트명으로 slug 생성 (import 스크립트와 동일 로직)."""
    import re
    base = name.lower().strip()
    base = re.sub(r'[^\w\s-]', '', base)
    base = re.sub(r'\s+', '-', base)
    base = base[:50]

    # Find matching slug with index
    for i in range(1000):
        slug = f"ner-{base}-{i:06d}"
        if slug in index:
            return slug
    return None


def link_sources_v2(test_limit=None, max_sources_per_event=50):
    """NER 이벤트와 소스 연결 (V2: first_source 기반 매칭)."""
    import re

    print("=" * 60)
    print("NER Event-Source Linking V2")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # Build source index
    print("\nBuilding source index...")
    source_index = build_source_index(conn)

    # Build NER JSON index by first_source
    print("\nBuilding NER JSON index...")
    ner_events = load_ner_events()

    # Index: first_source -> source_docs list
    ner_by_first_source = {}
    for evt in ner_events:
        source_docs = evt.get('source_docs', [])
        if source_docs:
            first_src = source_docs[0]
            ner_by_first_source[first_src] = source_docs

    print(f"  NER index: {len(ner_by_first_source):,} entries")

    # Get DB NER events
    print("\nLoading DB NER events...")
    cur.execute('''
        SELECT id, title, description
        FROM events
        WHERE slug LIKE 'ner-%%' AND slug NOT LIKE 'merged-%%'
        AND description IS NOT NULL
    ''')
    db_events = cur.fetchall()
    print(f"  DB NER events: {len(db_events):,}")

    if test_limit:
        db_events = db_events[:test_limit]
        print(f"  Test mode: processing {len(db_events)} events")

    # Process events
    print(f"\nLinking sources (max {max_sources_per_event} per event)...")

    linked = 0
    skipped_no_first_source = 0
    skipped_no_match = 0
    total_mentions = 0

    for i, (event_id, title, description) in enumerate(db_events):
        if i > 0 and i % 5000 == 0:
            conn.commit()
            print(f"  Progress: {i:,} / {len(db_events):,} ({linked:,} linked, {total_mentions:,} mentions)")

        # Parse first_source from description
        match = re.search(r'first_source=([^,\s]+)', description or '')
        if not match:
            skipped_no_first_source += 1
            continue

        first_source = match.group(1)

        # Find source_docs in NER JSON
        source_docs = ner_by_first_source.get(first_source)
        if not source_docs:
            # Try with just first_source as single source
            source_docs = [first_source]

        # Link sources
        mentions_added = 0
        for doc_id in source_docs[:max_sources_per_event]:
            source_id = source_index.get(doc_id)
            if not source_id:
                continue

            try:
                cur.execute('''
                    INSERT INTO text_mentions
                    (entity_type, entity_id, source_id, mention_text, confidence, extraction_model, extracted_at)
                    VALUES ('event', %s, %s, %s, 0.8, 'ner_link_v2', NOW())
                    ON CONFLICT DO NOTHING
                ''', (event_id, source_id, title))
                if cur.rowcount > 0:
                    mentions_added += 1
                    total_mentions += 1
            except Exception as e:
                pass

        if mentions_added > 0:
            linked += 1

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Events linked: {linked:,}")
    print(f"Total mentions added: {total_mentions:,}")
    print(f"Skipped (no first_source): {skipped_no_first_source:,}")


def link_sources(test_limit=None, max_sources_per_event=20):
    """NER 이벤트와 소스 연결 (레거시, V2 사용 권장)."""
    # Call V2 instead
    link_sources_v2(test_limit, max_sources_per_event)


def main():
    parser = argparse.ArgumentParser(description='Link NER events to sources')
    parser.add_argument('--test', type=int, metavar='N', help='Test with N events')
    parser.add_argument('--max-sources', type=int, default=20, help='Max sources per event (default: 20)')
    parser.add_argument('--full', action='store_true', help='Process all events')

    args = parser.parse_args()

    if args.test:
        link_sources(test_limit=args.test, max_sources_per_event=args.max_sources)
    elif args.full:
        link_sources(max_sources_per_event=args.max_sources)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
