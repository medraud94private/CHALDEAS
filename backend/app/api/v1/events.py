"""
Events API endpoints.

Provides access to historical events data from PostgreSQL database.
Events are the core data type in CHALDEAS, representing
occurrences in time and space.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.services import event_service, category_service

router = APIRouter()


def event_to_dict(event) -> dict:
    """Convert Event model to dictionary for JSON response."""
    location = event.primary_location
    return {
        "id": event.id,
        "title": event.title,
        "title_ko": event.title_ko,
        "slug": event.slug,
        "description": event.description,
        "date_start": event.date_start,
        "date_end": event.date_end,
        "importance": event.importance or 3,
        "category": {
            "id": event.category.id,
            "slug": event.category.slug,
            "name": event.category.name,
        } if event.category else None,
        "location": {
            "id": location.id,
            "name": location.name,
            "latitude": float(location.latitude) if location.latitude else None,
            "longitude": float(location.longitude) if location.longitude else None,
        } if location else None,
        "latitude": float(location.latitude) if location and location.latitude else None,
        "longitude": float(location.longitude) if location and location.longitude else None,
        "wikipedia_url": event.wikipedia_url,
        "image_url": event.image_url,
    }


@router.get("")
async def list_events(
    db: Session = Depends(get_db),
    year_start: Optional[int] = Query(None, description="Start year (negative for BCE)"),
    year_end: Optional[int] = Query(None, description="End year (negative for BCE)"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    importance_min: Optional[int] = Query(None, description="Minimum importance (1-5)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    List events with optional filtering.

    Used by the globe view to display event markers.
    Supports temporal and categorical filtering.
    """
    # If category slug provided, convert to category_id
    if category and not category_id:
        cat = category_service.get_category_by_slug(db, category)
        if cat:
            category_id = cat.id

    events, total = event_service.get_events(
        db,
        year_start=year_start,
        year_end=year_end,
        category_id=category_id,
        importance_min=importance_min,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [event_to_dict(e) for e in events],
        "total": total,
        "filtered": len(events),
    }


@router.get("/map")
async def get_events_for_map(
    db: Session = Depends(get_db),
    year: Optional[int] = Query(None, description="Center year for filtering"),
    year_range: int = Query(50, description="Range around center year"),
    limit: int = Query(500, ge=1, le=2000),
):
    """
    Get events formatted for map display.

    Returns simplified event data with just coordinates and essential info.
    """
    year_start = year - year_range if year else None
    year_end = year + year_range if year else None

    events, _ = event_service.get_events(
        db,
        year_start=year_start,
        year_end=year_end,
        limit=limit,
    )

    markers = []
    for e in events:
        loc = e.primary_location
        if loc and loc.latitude and loc.longitude:
            markers.append({
                "id": e.id,
                "title": e.title,
                "date": e.date_start,
                "lat": float(loc.latitude),
                "lng": float(loc.longitude),
                "category": e.category.slug if e.category else "general",
                "importance": e.importance or 3,
            })

    return {"markers": markers, "count": len(markers)}


@router.get("/stats")
async def get_event_stats(db: Session = Depends(get_db)):
    """Get statistics about events data."""
    from sqlalchemy import func
    from app.models.event import Event
    from app.models.location import Location

    total = db.query(func.count(Event.id)).scalar()
    with_location = db.query(func.count(Event.id)).filter(Event.primary_location_id.isnot(None)).scalar()

    return {
        "events": total,
        "events_with_coords": with_location,
    }


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific event.

    Includes related persons, locations, and sources.
    This data is displayed in the wiki panel (LAPLACE output).
    """
    event = event_service.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = event_to_dict(event)

    # Add related data
    result["persons"] = [
        {"id": p.id, "name": p.name, "slug": p.slug}
        for p in event.persons
    ]
    result["locations"] = [
        {
            "id": l.id,
            "name": l.name,
            "latitude": float(l.latitude) if l.latitude else None,
            "longitude": float(l.longitude) if l.longitude else None,
        }
        for l in event.locations
    ]

    return result
