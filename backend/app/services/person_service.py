"""Person service - CRUD operations for persons."""
from sqlalchemy.orm import Session
from sqlalchemy import and_, not_, or_
from typing import Optional

from app.models.person import Person

# Noise patterns to exclude (honorifics without real names)
NOISE_PATTERNS = [
    "Mrs.%", "Mrs %", "Miss %", "Mr. %", "Mr %",
    "Sig.%", "Sig %", "Junr%", "Senr%",
    "Madame %", "Mme.%", "Mlle.%",
]


def get_persons(
    db: Session,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    category_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    include_noise: bool = False,
    include_orphans: bool = False,
) -> tuple[list[Person], int]:
    """Get persons with optional filtering."""
    query = db.query(Person)

    # Exclude noise data by default
    if not include_noise:
        noise_filters = [Person.name.ilike(p) for p in NOISE_PATTERNS]
        query = query.filter(not_(or_(*noise_filters)))

    # Exclude orphans (entities with no connections) by default
    if not include_orphans:
        query = query.filter(Person.connection_count > 0)

    if category_id is not None:
        query = query.filter(Person.category_id == category_id)
    if year_start is not None:
        query = query.filter(Person.death_year >= year_start)
    if year_end is not None:
        query = query.filter(Person.birth_year <= year_end)

    total = query.count()
    persons = query.order_by(Person.birth_year).offset(offset).limit(limit).all()

    return persons, total


def get_person_by_id(db: Session, person_id: int) -> Optional[Person]:
    return db.query(Person).filter(Person.id == person_id).first()


def get_person_events(db: Session, person_id: int) -> list:
    person = get_person_by_id(db, person_id)
    return person.events if person else []


def get_related_persons(
    db: Session,
    person_id: int,
    limit: int = 20,
    min_strength: float = 0,
) -> list[dict]:
    """
    Get related persons from person_relationships table.

    Returns list of dicts with:
    - id, name, name_ko, birth_year, death_year
    - strength, time_distance, relationship_type
    """
    from sqlalchemy import text

    query = text("""
        SELECT
            p.id,
            p.name,
            p.name_ko,
            p.birth_year,
            p.death_year,
            pr.strength,
            pr.time_distance,
            pr.relationship_type,
            pr.is_bidirectional
        FROM person_relationships pr
        JOIN persons p ON p.id = pr.related_person_id
        WHERE pr.person_id = :person_id
          AND pr.strength >= :min_strength

        UNION

        SELECT
            p.id,
            p.name,
            p.name_ko,
            p.birth_year,
            p.death_year,
            pr.strength,
            pr.time_distance,
            pr.relationship_type,
            pr.is_bidirectional
        FROM person_relationships pr
        JOIN persons p ON p.id = pr.person_id
        WHERE pr.related_person_id = :person_id
          AND pr.strength >= :min_strength

        ORDER BY strength DESC
        LIMIT :limit
    """)

    result = db.execute(query, {
        "person_id": person_id,
        "min_strength": min_strength,
        "limit": limit
    })

    relations = []
    for row in result:
        relations.append({
            "id": row[0],
            "name": row[1],
            "name_ko": row[2],
            "birth_year": row[3],
            "death_year": row[4],
            "strength": row[5],
            "time_distance": row[6],
            "relationship_type": row[7],
            "is_bidirectional": row[8],
        })

    return relations
