#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
오탐 관계 정리

너무 일반적인 이름이나 잘못된 엔티티로 인한 false positive 관계 삭제

Usage:
    python cleanup_false_positives.py --dry-run
    python cleanup_false_positives.py --apply
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import argparse
import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host='localhost', dbname='chaldeas', user='chaldeas',
        password='chaldeas_dev', port=5432
    )


# 오탐으로 분류할 person 이름 (정확히 일치)
FALSE_POSITIVE_EXACT = [
    'Other',
    'Commons',
    'London',
    'Count',
    'Museum',
    'Index',
    'List',
    'Table',
    'Category',
]

# 너무 짧거나 일반적인 이름 (단독 사용시 오탐)
TOO_GENERIC = [
    'William',
    'Henry',
    'Elizabeth',
    'Charles',
    'John',
    'James',
    'George',
    'Thomas',
    'Mary',
    'Anne',
]


def cleanup_false_positives(dry_run=True):
    conn = get_db_connection()
    cur = conn.cursor()

    print("=" * 60)
    print("오탐 관계 정리")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    total_deleted = 0

    # 1. 정확히 일치하는 오탐 이름
    print("\n=== 정확히 일치하는 오탐 ===")
    for name in FALSE_POSITIVE_EXACT:
        cur.execute("SELECT id FROM persons WHERE name = %s", (name,))
        result = cur.fetchone()
        if not result:
            continue

        person_id = result[0]

        # 관계 수 확인
        cur.execute("SELECT COUNT(*) FROM person_relationships WHERE person_id = %s OR related_person_id = %s",
                   (person_id, person_id))
        pr_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM event_persons WHERE person_id = %s", (person_id,))
        ep_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM person_locations WHERE person_id = %s", (person_id,))
        pl_count = cur.fetchone()[0]

        total = pr_count + ep_count + pl_count
        print(f"  {name} (id={person_id}): {total:,} relationships")

        if not dry_run:
            cur.execute("DELETE FROM person_relationships WHERE person_id = %s OR related_person_id = %s",
                       (person_id, person_id))
            cur.execute("DELETE FROM event_persons WHERE person_id = %s", (person_id,))
            cur.execute("DELETE FROM person_locations WHERE person_id = %s", (person_id,))
            conn.commit()
            print(f"    -> Deleted")

        total_deleted += total

    # 2. 단독 이름 (성 없이 이름만)으로 된 일반적인 이름
    print("\n=== 너무 일반적인 단독 이름 ===")
    for name in TOO_GENERIC:
        cur.execute("SELECT id FROM persons WHERE name = %s", (name,))
        result = cur.fetchone()
        if not result:
            continue

        person_id = result[0]

        cur.execute("SELECT COUNT(*) FROM person_relationships WHERE person_id = %s OR related_person_id = %s",
                   (person_id, person_id))
        pr_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM event_persons WHERE person_id = %s", (person_id,))
        ep_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM person_locations WHERE person_id = %s", (person_id,))
        pl_count = cur.fetchone()[0]

        total = pr_count + ep_count + pl_count
        print(f"  {name} (id={person_id}): {total:,} relationships")

        if not dry_run:
            cur.execute("DELETE FROM person_relationships WHERE person_id = %s OR related_person_id = %s",
                       (person_id, person_id))
            cur.execute("DELETE FROM event_persons WHERE person_id = %s", (person_id,))
            cur.execute("DELETE FROM person_locations WHERE person_id = %s", (person_id,))
            conn.commit()
            print(f"    -> Deleted")

        total_deleted += total

    print(f"\n총 삭제 대상: {total_deleted:,} relationships")

    if dry_run:
        print("\n[DRY RUN] 실제 삭제는 --apply 옵션으로 실행하세요.")
    else:
        # 최종 현황
        cur.execute("SELECT COUNT(*) FROM person_relationships")
        print(f"\n최종 person_relationships: {cur.fetchone()[0]:,}")
        cur.execute("SELECT COUNT(*) FROM event_persons")
        print(f"최종 event_persons: {cur.fetchone()[0]:,}")

    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    dry_run = not args.apply
    cleanup_false_positives(dry_run=dry_run)


if __name__ == "__main__":
    main()
