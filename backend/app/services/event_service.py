"""
Event service - CRUD operations for events.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional

from app.models.event import Event


def get_events(
    db: Session,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    category_id: Optional[int] = None,
    importance_min: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Event], int]:
    """Get events with optional filtering."""
    query = db.query(Event)

    # Apply filters
    if year_start is not None:
        query = query.filter(Event.date_start >= year_start)
    if year_end is not None:
        query = query.filter(
            or_(
                Event.date_end <= year_end,
                and_(Event.date_end.is_(None), Event.date_start <= year_end)
            )
        )
    if category_id is not None:
        query = query.filter(Event.category_id == category_id)
    if importance_min is not None:
        query = query.filter(Event.importance >= importance_min)

    # Get total count
    total = query.count()

    # Apply pagination
    events = query.order_by(Event.date_start).offset(offset).limit(limit).all()

    return events, total


def get_event_by_id(db: Session, event_id: int) -> Optional[Event]:
    """Get single event by ID."""
    return db.query(Event).filter(Event.id == event_id).first()


def get_event_by_slug(db: Session, slug: str) -> Optional[Event]:
    """Get single event by slug."""
    return db.query(Event).filter(Event.slug == slug).first()
