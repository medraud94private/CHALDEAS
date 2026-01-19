#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compact DB 생성 스크립트

원본 DB를 Compact 버전으로 변환합니다.
- 고아 엔티티 제거 (connection_count = 0)
- 파이프라인 전용 테이블 제거 (gazetteer, text_mentions, embeddings)
- 백업 테이블 제거

Usage:
    python create-compact-db.py --dry-run     # 분석만 (변경 없음)
    python create-compact-db.py --execute     # 실행 (원본 DB 수정)
    python create-compact-db.py --dump-only   # 현재 상태 덤프만 생성

주의:
    --execute는 원본 DB를 직접 수정합니다.
    Full 버전 복원이 필요하면 미리 백업하세요:
    pg_dump -Fc chaldeas > chaldeas_full_backup.dump
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2


# 데이터베이스 설정
DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'chaldeas',
    'user': 'chaldeas',
    'password': 'chaldeas_dev',
    'port': 5432
}

# 제거할 테이블 (파이프라인 전용)
TABLES_TO_DROP = [
    'gazetteer',
    'text_mentions',
    'embeddings',
]


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def analyze_db(cur):
    """현재 DB 상태 분석"""
    print("=" * 60)
    print("Compact DB 분석")
    print("=" * 60)
    print()

    total_savings = 0

    # 1. 고아 엔티티
    print("1. 고아 엔티티 (connection_count = 0)")
    for table in ['events', 'persons', 'locations']:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE connection_count = 0 OR connection_count IS NULL")
        orphans = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT pg_total_relation_size('{table}')")
        size_bytes = cur.fetchone()[0]

        if total > 0:
            orphan_bytes = int(size_bytes * orphans / total)
            total_savings += orphan_bytes
            print(f"   {table}: {orphans:,} / {total:,} ({orphan_bytes // 1024 // 1024} MB)")

    print()

    # 2. 파이프라인 전용 테이블
    print("2. 파이프라인 전용 테이블")
    for table in TABLES_TO_DROP:
        try:
            cur.execute(f"SELECT pg_total_relation_size('{table}')")
            size_bytes = cur.fetchone()[0]
            total_savings += size_bytes
            print(f"   {table}: {size_bytes // 1024 // 1024} MB")
        except:
            cur.connection.rollback()
            print(f"   {table}: (없음)")

    print()

    # 3. 백업 테이블
    print("3. 백업 테이블")
    cur.execute("""
        SELECT relname, pg_total_relation_size(relid)
        FROM pg_statio_user_tables
        WHERE relname LIKE '%backup%'
    """)
    backups = cur.fetchall()
    for name, size_bytes in backups:
        total_savings += size_bytes
        print(f"   {name}: {size_bytes // 1024 // 1024} MB")

    if not backups:
        print("   (없음)")

    print()

    # 현재 DB 크기
    cur.execute(f"SELECT pg_database_size('{DB_CONFIG['dbname']}')")
    current_size = cur.fetchone()[0]

    print(f"예상 절감: {total_savings // 1024 // 1024:,} MB")
    print(f"현재 크기: {current_size // 1024 // 1024:,} MB")
    print(f"Compact 예상: {(current_size - total_savings) // 1024 // 1024:,} MB")

    return total_savings


def execute_compact(cur, conn):
    """Compact 변환 실행"""
    print()
    print("=" * 60)
    print("Compact 변환 실행")
    print("=" * 60)
    print()

    # 1. 고아 엔티티 삭제
    print("1. 고아 엔티티 삭제")

    # 먼저 관계 테이블에서 참조 삭제
    print("   1.1 관계 정리 중...")

    # event_persons에서 고아 이벤트/인물 참조 삭제
    cur.execute("""
        DELETE FROM event_persons
        WHERE event_id IN (SELECT id FROM events WHERE connection_count = 0)
        OR person_id IN (SELECT id FROM persons WHERE connection_count = 0)
    """)
    print(f"       event_persons: {cur.rowcount} rows")

    # event_locations에서 고아 참조 삭제
    cur.execute("""
        DELETE FROM event_locations
        WHERE event_id IN (SELECT id FROM events WHERE connection_count = 0)
        OR location_id IN (SELECT id FROM locations WHERE connection_count = 0)
    """)
    print(f"       event_locations: {cur.rowcount} rows")

    # person_locations에서 고아 참조 삭제
    cur.execute("""
        DELETE FROM person_locations
        WHERE person_id IN (SELECT id FROM persons WHERE connection_count = 0)
        OR location_id IN (SELECT id FROM locations WHERE connection_count = 0)
    """)
    print(f"       person_locations: {cur.rowcount} rows")

    # person_relationships에서 고아 참조 삭제
    cur.execute("""
        DELETE FROM person_relationships
        WHERE person_id IN (SELECT id FROM persons WHERE connection_count = 0)
        OR related_person_id IN (SELECT id FROM persons WHERE connection_count = 0)
    """)
    print(f"       person_relationships: {cur.rowcount} rows")

    conn.commit()

    print("   1.2 엔티티 삭제 중...")
    for table in ['events', 'persons', 'locations']:
        cur.execute(f"DELETE FROM {table} WHERE connection_count = 0 OR connection_count IS NULL")
        deleted = cur.rowcount
        print(f"       {table}: {deleted:,} rows")
    conn.commit()

    # 2. 파이프라인 전용 테이블 삭제
    print()
    print("2. 파이프라인 전용 테이블 삭제")
    for table in TABLES_TO_DROP:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"   {table}: 삭제됨")
        except Exception as e:
            conn.rollback()
            print(f"   {table}: 에러 - {e}")
    conn.commit()

    # 3. 백업 테이블 삭제
    print()
    print("3. 백업 테이블 삭제")
    cur.execute("""
        SELECT relname FROM pg_statio_user_tables
        WHERE relname LIKE '%backup%'
    """)
    for (name,) in cur.fetchall():
        cur.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
        print(f"   {name}: 삭제됨")
    conn.commit()

    # 4. VACUUM
    print()
    print("4. VACUUM FULL 실행 중... (시간이 걸릴 수 있습니다)")
    conn.autocommit = True
    cur.execute("VACUUM FULL")
    conn.autocommit = False
    print("   완료")

    # 5. 최종 크기
    cur.execute(f"SELECT pg_database_size('{DB_CONFIG['dbname']}')")
    final_size = cur.fetchone()[0]
    print()
    print(f"최종 크기: {final_size // 1024 // 1024:,} MB")


def create_dump(filename=None):
    """덤프 파일 생성"""
    print()
    print("=" * 60)
    print("덤프 파일 생성")
    print("=" * 60)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chaldeas_compact_{timestamp}.dump"

    print(f"파일: {filename}")

    cmd = [
        'pg_dump',
        '-h', DB_CONFIG['host'],
        '-p', str(DB_CONFIG['port']),
        '-U', DB_CONFIG['user'],
        '-d', DB_CONFIG['dbname'],
        '-Fc',  # custom format
        '-f', filename
    ]

    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']

    print("생성 중...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        size = os.path.getsize(filename)
        print(f"완료: {size // 1024 // 1024} MB")
        return filename
    else:
        print(f"에러: {result.stderr}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Compact DB 생성',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python create-compact-db.py --dry-run      # 분석만
  python create-compact-db.py --execute      # Compact 변환
  python create-compact-db.py --dump-only    # 현재 상태 덤프

주의: --execute는 원본 DB를 직접 수정합니다!
        """
    )
    parser.add_argument('--dry-run', action='store_true', help='분석만 (변경 없음)')
    parser.add_argument('--execute', action='store_true', help='Compact 변환 실행')
    parser.add_argument('--dump-only', action='store_true', help='현재 상태 덤프만 생성')
    parser.add_argument('--output', '-o', help='덤프 파일명')
    args = parser.parse_args()

    if not any([args.dry_run, args.execute, args.dump_only]):
        args.dry_run = True

    conn = get_connection()
    cur = conn.cursor()

    # 분석
    analyze_db(cur)

    if args.dry_run:
        print()
        print("[DRY RUN] --execute로 실제 실행, --dump-only로 덤프 생성")
        conn.close()
        return

    if args.dump_only:
        conn.close()
        create_dump(args.output)
        return

    if args.execute:
        print()
        confirm = input("원본 DB를 수정합니다. 계속하시겠습니까? (yes/no): ")
        if confirm.lower() != 'yes':
            print("취소됨")
            conn.close()
            return

        execute_compact(cur, conn)
        conn.close()

        # 덤프 생성
        create_dump(args.output)

        print()
        print("=" * 60)
        print("완료!")
        print("=" * 60)


if __name__ == '__main__':
    main()
