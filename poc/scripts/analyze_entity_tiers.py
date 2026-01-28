#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
엔티티 티어 분석 및 분류

연결 수 기반으로 엔티티를 티어로 분류:
- Tier S: 연결 50+개 (핵심 인물/이벤트)
- Tier A: 연결 20-49개
- Tier B: 연결 5-19개
- Tier C: 연결 1-4개
- Tier D: 연결 0개 (고아 엔티티)

Usage:
    python analyze_entity_tiers.py
    python analyze_entity_tiers.py --export-orphans
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import json
import argparse
from pathlib import Path
from collections import defaultdict

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


def analyze_persons(conn):
    """Person 연결 분석"""
    print("\n" + "=" * 60)
    print("PERSONS 티어 분석")
    print("=" * 60)

    cur = conn.cursor()

    # 각 person의 연결 수 계산
    cur.execute("""
        SELECT p.id, p.name,
            COALESCE(pr.rel_count, 0) + COALESCE(ep.event_count, 0) + COALESCE(pl.loc_count, 0) as total_connections
        FROM persons p
        LEFT JOIN (
            SELECT person_id, COUNT(*) as rel_count
            FROM person_relationships
            GROUP BY person_id
        ) pr ON p.id = pr.person_id
        LEFT JOIN (
            SELECT person_id, COUNT(*) as event_count
            FROM event_persons
            GROUP BY person_id
        ) ep ON p.id = ep.person_id
        LEFT JOIN (
            SELECT person_id, COUNT(*) as loc_count
            FROM person_locations
            GROUP BY person_id
        ) pl ON p.id = pl.person_id
    """)

    results = cur.fetchall()

    tiers = {'S': [], 'A': [], 'B': [], 'C': [], 'D': []}

    for pid, name, total in results:
        if total >= 50:
            tiers['S'].append((pid, name, total))
        elif total >= 20:
            tiers['A'].append((pid, name, total))
        elif total >= 5:
            tiers['B'].append((pid, name, total))
        elif total >= 1:
            tiers['C'].append((pid, name, total))
        else:
            tiers['D'].append((pid, name, total))

    total_persons = len(results)
    print(f"\n총 Persons: {total_persons:,}")
    print("\n티어별 분포:")
    print(f"  Tier S (50+):  {len(tiers['S']):,} ({len(tiers['S'])/total_persons*100:.1f}%)")
    print(f"  Tier A (20-49): {len(tiers['A']):,} ({len(tiers['A'])/total_persons*100:.1f}%)")
    print(f"  Tier B (5-19):  {len(tiers['B']):,} ({len(tiers['B'])/total_persons*100:.1f}%)")
    print(f"  Tier C (1-4):   {len(tiers['C']):,} ({len(tiers['C'])/total_persons*100:.1f}%)")
    print(f"  Tier D (0):     {len(tiers['D']):,} ({len(tiers['D'])/total_persons*100:.1f}%)")

    # Top 10 S tier
    if tiers['S']:
        print("\nTop 10 Tier S Persons:")
        for pid, name, total in sorted(tiers['S'], key=lambda x: -x[2])[:10]:
            print(f"  {name}: {total} connections")

    return tiers


def analyze_events(conn):
    """Event 연결 분석"""
    print("\n" + "=" * 60)
    print("EVENTS 티어 분석")
    print("=" * 60)

    cur = conn.cursor()

    cur.execute("""
        SELECT e.id, e.title,
            COALESCE(ep.person_count, 0) + COALESCE(el.loc_count, 0) as total_connections
        FROM events e
        LEFT JOIN (
            SELECT event_id, COUNT(*) as person_count
            FROM event_persons
            GROUP BY event_id
        ) ep ON e.id = ep.event_id
        LEFT JOIN (
            SELECT event_id, COUNT(*) as loc_count
            FROM event_locations
            GROUP BY event_id
        ) el ON e.id = el.event_id
    """)

    results = cur.fetchall()

    tiers = {'S': [], 'A': [], 'B': [], 'C': [], 'D': []}

    for eid, title, total in results:
        if total >= 50:
            tiers['S'].append((eid, title, total))
        elif total >= 20:
            tiers['A'].append((eid, title, total))
        elif total >= 5:
            tiers['B'].append((eid, title, total))
        elif total >= 1:
            tiers['C'].append((eid, title, total))
        else:
            tiers['D'].append((eid, title, total))

    total_events = len(results)
    print(f"\n총 Events: {total_events:,}")
    print("\n티어별 분포:")
    print(f"  Tier S (50+):  {len(tiers['S']):,} ({len(tiers['S'])/total_events*100:.1f}%)")
    print(f"  Tier A (20-49): {len(tiers['A']):,} ({len(tiers['A'])/total_events*100:.1f}%)")
    print(f"  Tier B (5-19):  {len(tiers['B']):,} ({len(tiers['B'])/total_events*100:.1f}%)")
    print(f"  Tier C (1-4):   {len(tiers['C']):,} ({len(tiers['C'])/total_events*100:.1f}%)")
    print(f"  Tier D (0):     {len(tiers['D']):,} ({len(tiers['D'])/total_events*100:.1f}%)")

    if tiers['S']:
        print("\nTop 10 Tier S Events:")
        for eid, title, total in sorted(tiers['S'], key=lambda x: -x[2])[:10]:
            print(f"  {title[:50]}: {total} connections")

    return tiers


def analyze_locations(conn):
    """Location 연결 분석"""
    print("\n" + "=" * 60)
    print("LOCATIONS 티어 분석")
    print("=" * 60)

    cur = conn.cursor()

    cur.execute("""
        SELECT l.id, l.name,
            COALESCE(pl.person_count, 0) + COALESCE(el.event_count, 0) as total_connections
        FROM locations l
        LEFT JOIN (
            SELECT location_id, COUNT(*) as person_count
            FROM person_locations
            GROUP BY location_id
        ) pl ON l.id = pl.location_id
        LEFT JOIN (
            SELECT location_id, COUNT(*) as event_count
            FROM event_locations
            GROUP BY location_id
        ) el ON l.id = el.location_id
    """)

    results = cur.fetchall()

    tiers = {'S': [], 'A': [], 'B': [], 'C': [], 'D': []}

    for lid, name, total in results:
        if total >= 50:
            tiers['S'].append((lid, name, total))
        elif total >= 20:
            tiers['A'].append((lid, name, total))
        elif total >= 5:
            tiers['B'].append((lid, name, total))
        elif total >= 1:
            tiers['C'].append((lid, name, total))
        else:
            tiers['D'].append((lid, name, total))

    total_locs = len(results)
    print(f"\n총 Locations: {total_locs:,}")
    print("\n티어별 분포:")
    print(f"  Tier S (50+):  {len(tiers['S']):,} ({len(tiers['S'])/total_locs*100:.1f}%)")
    print(f"  Tier A (20-49): {len(tiers['A']):,} ({len(tiers['A'])/total_locs*100:.1f}%)")
    print(f"  Tier B (5-19):  {len(tiers['B']):,} ({len(tiers['B'])/total_locs*100:.1f}%)")
    print(f"  Tier C (1-4):   {len(tiers['C']):,} ({len(tiers['C'])/total_locs*100:.1f}%)")
    print(f"  Tier D (0):     {len(tiers['D']):,} ({len(tiers['D'])/total_locs*100:.1f}%)")

    if tiers['S']:
        print("\nTop 10 Tier S Locations:")
        for lid, name, total in sorted(tiers['S'], key=lambda x: -x[2])[:10]:
            print(f"  {name}: {total} connections")

    return tiers


def export_orphans(person_tiers, event_tiers, location_tiers):
    """고아 엔티티 내보내기"""
    output_dir = Path(__file__).parent.parent / "data" / "tier_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persons
    with open(output_dir / "orphan_persons.jsonl", 'w', encoding='utf-8') as f:
        for pid, name, _ in person_tiers['D']:
            f.write(json.dumps({'id': pid, 'name': name}, ensure_ascii=False) + '\n')
    print(f"\nExported {len(person_tiers['D']):,} orphan persons")

    # Events
    with open(output_dir / "orphan_events.jsonl", 'w', encoding='utf-8') as f:
        for eid, title, _ in event_tiers['D']:
            f.write(json.dumps({'id': eid, 'title': title}, ensure_ascii=False) + '\n')
    print(f"Exported {len(event_tiers['D']):,} orphan events")

    # Locations
    with open(output_dir / "orphan_locations.jsonl", 'w', encoding='utf-8') as f:
        for lid, name, _ in location_tiers['D']:
            f.write(json.dumps({'id': lid, 'name': name}, ensure_ascii=False) + '\n')
    print(f"Exported {len(location_tiers['D']):,} orphan locations")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-orphans", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("엔티티 티어 분석")
    print("=" * 60)

    conn = get_db_connection()

    person_tiers = analyze_persons(conn)
    event_tiers = analyze_events(conn)
    location_tiers = analyze_locations(conn)

    if args.export_orphans:
        export_orphans(person_tiers, event_tiers, location_tiers)

    # Summary
    print("\n" + "=" * 60)
    print("전체 요약")
    print("=" * 60)

    total_orphans = len(person_tiers['D']) + len(event_tiers['D']) + len(location_tiers['D'])
    total_entities = sum(len(t) for t in person_tiers.values()) + \
                    sum(len(t) for t in event_tiers.values()) + \
                    sum(len(t) for t in location_tiers.values())

    print(f"총 엔티티: {total_entities:,}")
    print(f"고아 엔티티 (Tier D): {total_orphans:,} ({total_orphans/total_entities*100:.1f}%)")
    print(f"연결된 엔티티: {total_entities - total_orphans:,} ({(total_entities-total_orphans)/total_entities*100:.1f}%)")

    conn.close()


if __name__ == "__main__":
    main()
