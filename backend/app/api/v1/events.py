"""
Events API endpoints.

Provides access to historical events data.
Events are the core data type in CHALDEAS, representing
occurrences in time and space.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.services.json_data import get_data_service

router = APIRouter()


@router.get("")
async def list_events(
    year_start: Optional[int] = Query(None, description="Start year (negative for BCE)"),
    year_end: Optional[int] = Query(None, description="End year (negative for BCE)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    List events with optional filtering.

    Used by the globe view to display event markers.
    Supports temporal and categorical filtering.
    """
    data_service = get_data_service()
    events = data_service.get_events(
        year_start=year_start,
        year_end=year_end,
        category=category,
        limit=limit,
        offset=offset,
    )
    return {
        "items": events,
        "total": len(data_service.events),
        "filtered": len(events),
    }


@router.get("/map")
async def get_events_for_map(
    year: Optional[int] = Query(None, description="Center year for filtering"),
    year_range: int = Query(50, description="Range around center year"),
):
    """
    Get events formatted for map display.

    Returns simplified event data with just coordinates and essential info.
    """
    data_service = get_data_service()
    markers = data_service.get_events_for_map(year=year, year_range=year_range)
    return {"markers": markers, "count": len(markers)}


@router.get("/stats")
async def get_event_stats():
    """Get statistics about events data."""
    data_service = get_data_service()
    return data_service.get_stats()


@router.get("/{event_id}")
async def get_event(event_id: str):
    """
    Get detailed information about a specific event.

    Includes related persons, locations, and sources.
    This data is displayed in the wiki panel (LAPLACE output).
    """
    data_service = get_data_service()
    event = data_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
