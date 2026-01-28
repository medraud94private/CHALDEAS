"""
Update persons.data_quality based on various criteria.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from sqlalchemy import text


def main():
    db = SessionLocal()

    print("=== Updating data_quality ===")

    # 1. verified: wikidata_id 있는 경우
    result = db.execute(text("""
        UPDATE persons
        SET data_quality = 'verified',
            source_type = 'wikidata',
            verified_at = NOW()
        WHERE wikidata_id IS NOT NULL
    """))
    print(f"verified (wikidata_id): {result.rowcount}")

    # 2. noise: 호칭 패턴
    result = db.execute(text("""
        UPDATE persons
        SET data_quality = 'noise'
        WHERE data_quality != 'verified'
        AND (
            name ILIKE 'Mrs.%' OR name ILIKE 'Mrs %' OR
            name ILIKE 'Miss %' OR name ILIKE 'Mr. %' OR
            name ILIKE 'Mr %' OR name ILIKE 'Sig.%' OR
            name ILIKE 'Sig %' OR name ILIKE 'Junr%' OR
            name ILIKE 'Senr%' OR name ILIKE 'Madame %' OR
            name ILIKE 'Mme.%' OR name ILIKE 'Mlle.%'
        )
    """))
    print(f"noise (honorific patterns): {result.rowcount}")

    # 3. sourced: 생몰년 있고 mention_count > 5
    result = db.execute(text("""
        UPDATE persons
        SET data_quality = 'sourced'
        WHERE data_quality = 'extracted'
        AND (birth_year IS NOT NULL OR death_year IS NOT NULL)
        AND mention_count > 5
    """))
    print(f"sourced (lifespan + mentions): {result.rowcount}")

    db.commit()

    # 확인
    result = db.execute(text("""
        SELECT data_quality, COUNT(*)
        FROM persons
        GROUP BY data_quality
        ORDER BY COUNT(*) DESC
    """))
    print("\n=== Distribution ===")
    for row in result:
        print(f"  {row[0]}: {row[1]:,}")

    db.close()


if __name__ == "__main__":
    main()
