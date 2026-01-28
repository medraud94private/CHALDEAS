"""
Phase 2: Wikipedia JSONL → DB 임포트

Phase 1 결과물(wikipedia_full/*.jsonl)을 DB에 임포트.

구조:
- 엔티티 테이블 (persons/events/locations): 기본 정보 + summary
- Sources 테이블: 전체 원문 (content)
- entity_sources 연결 테이블: 관계

Usage:
    python import_wikipedia_to_db.py --dry-run    # 테스트 (DB 변경 없음)
    python import_wikipedia_to_db.py --limit 100  # 100개만
    python import_wikipedia_to_db.py --full       # 전체 임포트
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
from pathlib import Path
from datetime import datetime

# DB 연결
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ============ Config ============

INPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia_full"
CHECKPOINT_FILE = INPUT_DIR / "import_checkpoint.json"

DATABASE_URL = "postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# ============ Checkpoint ============

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'persons': 0, 'events': 0, 'locations': 0}


def save_checkpoint(checkpoint: dict):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, indent=2)


# ============ Import Functions ============

def import_person(session, record: dict, dry_run: bool = False) -> bool:
    """Person 레코드 임포트"""

    # 중복 체크: qid 또는 (title + birth_year)
    qid = record.get('qid')
    title = record['title']
    birth_year = record.get('birth_year')

    if qid:
        existing = session.execute(
            text("SELECT id FROM persons WHERE wikidata_id = :qid"),
            {'qid': qid}
        ).fetchone()
        if existing:
            # 기존 레코드 업데이트 (biography, wikipedia_url 등)
            if not dry_run:
                session.execute(text("""
                    UPDATE persons SET
                        wikipedia_url = COALESCE(wikipedia_url, :url),
                        biography = COALESCE(biography, :bio),
                        updated_at = NOW()
                    WHERE wikidata_id = :qid
                """), {
                    'qid': qid,
                    'url': record.get('wikipedia_url'),
                    'bio': record.get('summary', '')[:2000]
                })
            return False  # 업데이트만, 새로 생성 아님

    # 새 레코드 생성
    if not dry_run:
        # 1. Person 테이블에 삽입
        result = session.execute(text("""
            INSERT INTO persons (name, wikidata_id, wikipedia_url, birth_year, death_year,
                                 biography, created_at, updated_at)
            VALUES (:name, :qid, :url, :birth, :death, :bio, NOW(), NOW())
            RETURNING id
        """), {
            'name': title,
            'qid': qid,
            'url': record.get('wikipedia_url'),
            'birth': birth_year,
            'death': record.get('death_year'),
            'bio': record.get('summary', '')[:2000]
        })
        person_id = result.fetchone()[0]

        # 2. Source 테이블에 원문 저장
        content = record.get('content', '')
        if content:
            source_result = session.execute(text("""
                INSERT INTO sources (title, url, archive_type, content, created_at, updated_at)
                VALUES (:title, :url, 'wikipedia', :content, NOW(), NOW())
                RETURNING id
            """), {
                'title': title,
                'url': record.get('wikipedia_url'),
                'content': content
            })
            source_id = source_result.fetchone()[0]

            # 3. person_sources 연결
            session.execute(text("""
                INSERT INTO person_sources (person_id, source_id)
                VALUES (:pid, :sid)
            """), {'pid': person_id, 'sid': source_id})

    return True  # 새로 생성


def import_event(session, record: dict, dry_run: bool = False) -> bool:
    """Event 레코드 임포트"""

    qid = record.get('qid')
    title = record['title']

    if qid:
        existing = session.execute(
            text("SELECT id FROM events WHERE wikidata_id = :qid"),
            {'qid': qid}
        ).fetchone()
        if existing:
            if not dry_run:
                session.execute(text("""
                    UPDATE events SET
                        wikipedia_url = COALESCE(wikipedia_url, :url),
                        description = COALESCE(description, :desc),
                        updated_at = NOW()
                    WHERE wikidata_id = :qid
                """), {
                    'qid': qid,
                    'url': record.get('wikipedia_url'),
                    'desc': record.get('summary', '')[:2000]
                })
            return False

    if not dry_run:
        result = session.execute(text("""
            INSERT INTO events (title, wikidata_id, wikipedia_url, date_start, date_end,
                               description, created_at, updated_at)
            VALUES (:title, :qid, :url, :start, :end, :desc, NOW(), NOW())
            RETURNING id
        """), {
            'title': title,
            'qid': qid,
            'url': record.get('wikipedia_url'),
            'start': record.get('start_year'),
            'end': record.get('end_year'),
            'desc': record.get('summary', '')[:2000]
        })
        event_id = result.fetchone()[0]

        content = record.get('content', '')
        if content:
            source_result = session.execute(text("""
                INSERT INTO sources (title, url, archive_type, content, created_at, updated_at)
                VALUES (:title, :url, 'wikipedia', :content, NOW(), NOW())
                RETURNING id
            """), {
                'title': title,
                'url': record.get('wikipedia_url'),
                'content': content
            })
            source_id = source_result.fetchone()[0]

            session.execute(text("""
                INSERT INTO event_sources (event_id, source_id)
                VALUES (:eid, :sid)
            """), {'eid': event_id, 'sid': source_id})

    return True


def import_location(session, record: dict, dry_run: bool = False) -> bool:
    """Location 레코드 임포트"""

    qid = record.get('qid')
    title = record['title']

    if qid:
        existing = session.execute(
            text("SELECT id FROM locations WHERE wikidata_id = :qid"),
            {'qid': qid}
        ).fetchone()
        if existing:
            if not dry_run:
                session.execute(text("""
                    UPDATE locations SET
                        wikipedia_url = COALESCE(wikipedia_url, :url),
                        description = COALESCE(description, :desc),
                        latitude = COALESCE(latitude, :lat),
                        longitude = COALESCE(longitude, :lon),
                        updated_at = NOW()
                    WHERE wikidata_id = :qid
                """), {
                    'qid': qid,
                    'url': record.get('wikipedia_url'),
                    'desc': record.get('summary', '')[:2000],
                    'lat': record.get('latitude'),
                    'lon': record.get('longitude')
                })
            return False

    if not dry_run:
        result = session.execute(text("""
            INSERT INTO locations (name, wikidata_id, wikipedia_url, latitude, longitude,
                                   description, created_at, updated_at)
            VALUES (:name, :qid, :url, :lat, :lon, :desc, NOW(), NOW())
            RETURNING id
        """), {
            'name': title,
            'qid': qid,
            'url': record.get('wikipedia_url'),
            'lat': record.get('latitude'),
            'lon': record.get('longitude'),
            'desc': record.get('summary', '')[:2000]
        })
        location_id = result.fetchone()[0]

        content = record.get('content', '')
        if content:
            source_result = session.execute(text("""
                INSERT INTO sources (title, url, archive_type, content, created_at, updated_at)
                VALUES (:title, :url, 'wikipedia', :content, NOW(), NOW())
                RETURNING id
            """), {
                'title': title,
                'url': record.get('wikipedia_url'),
                'content': content
            })
            source_id = source_result.fetchone()[0]

            session.execute(text("""
                INSERT INTO location_sources (location_id, source_id)
                VALUES (:lid, :sid)
            """), {'lid': location_id, 'sid': source_id})

    return True


# ============ Main ============

def import_all(entity_type: str, limit: int = None, dry_run: bool = False, resume: bool = True):
    """JSONL 파일에서 DB로 임포트"""

    filepath = INPUT_DIR / f"{entity_type}.jsonl"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return

    checkpoint = load_checkpoint() if resume else {}
    start_line = checkpoint.get(entity_type, 0)

    import_func = {
        'persons': import_person,
        'events': import_event,
        'locations': import_location
    }[entity_type]

    session = Session()

    stats = {'created': 0, 'updated': 0, 'errors': 0}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i < start_line:
                    continue

                if limit and (i - start_line) >= limit:
                    break

                try:
                    record = json.loads(line.strip())
                    is_new = import_func(session, record, dry_run)

                    if is_new:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1

                    # 1000개마다 커밋
                    if (i - start_line + 1) % 1000 == 0:
                        if not dry_run:
                            session.commit()
                        checkpoint[entity_type] = i + 1
                        save_checkpoint(checkpoint)
                        print(f"[{entity_type}] {i+1:,} processed: {stats['created']} created, {stats['updated']} updated")

                except Exception as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 5:
                        print(f"Error at line {i}: {e}")

        if not dry_run:
            session.commit()

        checkpoint[entity_type] = i + 1
        save_checkpoint(checkpoint)

    finally:
        session.close()

    print(f"\n=== {entity_type} Import Complete ===")
    print(f"Created: {stats['created']}")
    print(f"Updated: {stats['updated']}")
    print(f"Errors: {stats['errors']}")
    if dry_run:
        print("(DRY RUN - no changes made)")


def main():
    parser = argparse.ArgumentParser(description="Import Wikipedia JSONL to DB")
    parser.add_argument("--type", choices=['persons', 'events', 'locations', 'all'], default='all')
    parser.add_argument("--limit", type=int, help="Limit records per type")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually write to DB")
    parser.add_argument("--full", action="store_true", help="Import all records")
    parser.add_argument("--no-resume", action="store_true", help="Start from beginning")

    args = parser.parse_args()

    limit = None if args.full else (args.limit or 100)
    resume = not args.no_resume

    types = ['persons', 'events', 'locations'] if args.type == 'all' else [args.type]

    for entity_type in types:
        print(f"\n{'='*60}")
        print(f"Importing {entity_type}...")
        print(f"{'='*60}")
        import_all(entity_type, limit=limit, dry_run=args.dry_run, resume=resume)


if __name__ == "__main__":
    main()
