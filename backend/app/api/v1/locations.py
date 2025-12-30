"""
Locations API endpoints.

Provides CRUD operations for geographical locations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.location import Location, LocationList, LocationDetail
from app.services import location_service

router = APIRouter()


@router.get("", response_model=LocationList)
async def list_locations(
    type: Optional[str] = Query(None, description="Location type (city, region, landmark)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List locations with optional filtering."""
    locations, total = location_service.get_locations(
        db,
        location_type=type,
        limit=limit,
        offset=offset,
    )
    return LocationList(items=locations, total=total)


@router.get("/{location_id}", response_model=LocationDetail)
async def get_location(
    location_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information about a location."""
    location = location_service.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.get("/{location_id}/events")
async def get_location_events(
    location_id: int,
    year_start: Optional[int] = Query(None),
    year_end: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get events that occurred at a location."""
    events = location_service.get_location_events(
        db, location_id, year_start, year_end
    )
    return {"location_id": location_id, "events": events}
