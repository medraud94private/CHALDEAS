"""Person service - CRUD operations for persons."""
from sqlalchemy.orm import Session
from typing import Optional

from app.models.person import Person


def get_persons(
    db: Session,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    category_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Person], int]:
    """Get persons with optional filtering."""
    query = db.query(Person)

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
