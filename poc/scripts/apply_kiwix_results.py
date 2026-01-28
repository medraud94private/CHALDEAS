"""
Kiwix 결과를 DB에 적용

1. 정방향: reconcile_results.jsonl → persons 테이블 wikidata_id 업데이트
2. 역방향: wikipedia_persons/persons.jsonl → 새 인물 추가 + sources 연결

Usage:
    python apply_kiwix_results.py forward --dry-run     # 정방향 미리보기
    python apply_kiwix_results.py forward               # 정방향 적용
    python apply_kiwix_results.py reverse --dry-run     # 역방향 미리보기
    python apply_kiwix_results.py reverse               # 역방향 적용
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.models import Person, Source

# ============ Config ============

DATA_DIR = Path(__file__).parent.parent / "data"
RECONCILE_RESULTS = DATA_DIR / "reconcile_results.jsonl"
WIKIPEDIA_PERSONS = DATA_DIR / "wikipedia_persons" / "persons.jsonl"


# ============ Forward: Update existing persons ============

def apply_forward_results(dry_run: bool = False):
    """정방향 결과 적용 - 기존 persons의 wikidata_id 업데이트"""
    if not RECONCILE_RESULTS.exists():
        print(f"File not found: {RECONCILE_RESULTS}")
        return

    db = SessionLocal()

    try:
        # 결과 로드 (kiwix 매칭만)
        updates = []
        with open(RECONCILE_RESULTS, 'r', encoding='utf-8') as f:
            for line in f:
                result = json.loads(line)
                if result.get("source") == "kiwix" and result.get("status") == "matched":
                    qid = result.get("qid")
                    person_id = result.get("person_id")
                    if qid and person_id:
                        updates.append({
                            "person_id": person_id,
                            "person_name": result.get("person_name"),
                            "qid": qid,
                            "wiki_birth": result.get("wiki_birth"),
                            "wiki_death": result.get("wiki_death"),
                        })

        print(f"Found {len(updates)} persons to update")

        if dry_run:
            print("\n[DRY RUN] Sample updates:")
            for u in updates[:20]:
                print(f"  [{u['person_id']}] {u['person_name']} → {u['qid']}")
            return

        # 실제 업데이트
        updated = 0
        skipped = 0
        for u in updates:
            person = db.query(Person).filter(Person.id == u["person_id"]).first()
            if not person:
                skipped += 1
                continue

            # 기존 QID가 있고 다르면 skip (충돌)
            if person.wikidata_id and person.wikidata_id != u["qid"]:
                print(f"  [SKIP] {person.name}: existing QID {person.wikidata_id} != {u['qid']}")
                skipped += 1
                continue

            # 업데이트
            person.wikidata_id = u["qid"]
            if not person.wikipedia_url:
                person.wikipedia_url = f"https://en.wikipedia.org/wiki/{u['person_name'].replace(' ', '_')}"

            updated += 1

            if updated % 1000 == 0:
                db.commit()
                print(f"  Updated {updated}...")

        db.commit()
        print(f"\nCompleted: {updated} updated, {skipped} skipped")

    finally:
        db.close()


# ============ Reverse: Add new persons ============

def apply_reverse_results(dry_run: bool = False):
    """역방향 결과 적용 - Wikipedia에서 발견한 새 인물 추가"""
    if not WIKIPEDIA_PERSONS.exists():
        print(f"File not found: {WIKIPEDIA_PERSONS}")
        return

    db = SessionLocal()

    try:
        # 기존 QID 목록 로드
        existing_qids = set()
        for person in db.query(Person.wikidata_id).filter(Person.wikidata_id != None).all():
            existing_qids.add(person.wikidata_id)
        print(f"Existing persons with QID: {len(existing_qids)}")

        # 기존 이름 목록 (정확 매칭용)
        existing_names = set()
        for person in db.query(Person.name).all():
            existing_names.add(person.name.lower())
        print(f"Existing person names: {len(existing_names)}")

        # Wikipedia 인물 로드
        new_persons = []
        duplicates = 0
        no_qid = 0

        with open(WIKIPEDIA_PERSONS, 'r', encoding='utf-8') as f:
            for line in f:
                wp = json.loads(line)

                # QID 없으면 스킵
                if not wp.get("qid"):
                    no_qid += 1
                    continue

                # 이미 있으면 스킵
                if wp["qid"] in existing_qids:
                    duplicates += 1
                    continue

                # 이름으로도 체크
                if wp["title"].lower() in existing_names:
                    duplicates += 1
                    continue

                new_persons.append(wp)

        print(f"New persons to add: {len(new_persons)}")
        print(f"Duplicates skipped: {duplicates}")
        print(f"No QID skipped: {no_qid}")

        if dry_run:
            print("\n[DRY RUN] Sample new persons:")
            for p in new_persons[:20]:
                print(f"  {p['title']} ({p['qid']}) - {p.get('birth_year', '?')}~{p.get('death_year', '?')}")
            return

        # Wikipedia 소스 가져오거나 생성
        wiki_source = db.query(Source).filter(Source.name == "Wikipedia").first()
        if not wiki_source:
            wiki_source = Source(
                name="Wikipedia",
                source_type="encyclopedia",
                url="https://en.wikipedia.org",
                reliability_score=0.8,
                description="English Wikipedia - online encyclopedia"
            )
            db.add(wiki_source)
            db.commit()
            print(f"Created Wikipedia source (id={wiki_source.id})")

        # 새 인물 추가
        added = 0
        for wp in new_persons:
            person = Person(
                name=wp["title"],
                wikidata_id=wp["qid"],
                birth_year=wp.get("birth_year"),
                death_year=wp.get("death_year"),
                wikipedia_url=f"https://en.wikipedia.org/wiki/{wp['wikipedia_path']}",
                biography=wp.get("summary", "")[:1000] if wp.get("summary") else None,
                certainty="high",  # Wikipedia 소스
            )
            db.add(person)
            added += 1

            if added % 1000 == 0:
                db.commit()
                print(f"  Added {added}...")

        db.commit()
        print(f"\nCompleted: {added} new persons added")

    finally:
        db.close()


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(description="Apply Kiwix results to DB")
    parser.add_argument("direction", choices=["forward", "reverse"], help="forward=update existing, reverse=add new")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")

    args = parser.parse_args()

    if args.direction == "forward":
        apply_forward_results(args.dry_run)
    else:
        apply_reverse_results(args.dry_run)


if __name__ == "__main__":
    main()
