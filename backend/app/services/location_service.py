"""Location service - CRUD operations for locations."""
from sqlalchemy.orm import Session
from typing import Optional

from app.models.location import Location


def get_locations(
    db: Session,
    location_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Location], int]:
    """Get locations with optional filtering."""
    query = db.query(Location)

    if location_type:
        query = query.filter(Location.type == location_type)

    total = query.count()
    locations = query.offset(offset).limit(limit).all()

    return locations, total


def get_location_by_id(db: Session, location_id: int) -> Optional[Location]:
    return db.query(Location).filter(Location.id == location_id).first()


def get_location_events(
    db: Session,
    location_id: int,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
) -> list:
    location = get_location_by_id(db, location_id)
    if not location:
        return []

    events = location.events
    if year_start:
        events = [e for e in events if e.date_start >= year_start]
    if year_end:
        events = [e for e in events if e.date_start <= year_end]

    return events
