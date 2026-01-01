"""
Entity API Endpoints
CRUD for Persons, Locations, Events, Periods
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Person, Location, Event, Period

router = APIRouter()


# --- Persons ---

@router.get("/persons")
async def list_persons(
    search: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List persons with optional search."""
    query = select(Person)

    if search:
        query = query.where(Person.name.ilike(f"%{search}%"))

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/persons/{person_id}")
async def get_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific person."""
    query = select(Person).where(Person.id == person_id)
    result = await db.execute(query)
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


# --- Locations ---

@router.get("/locations")
async def list_locations(
    search: Optional[str] = None,
    hierarchy_level: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List locations with optional filters."""
    query = select(Location)

    if search:
        query = query.where(Location.name.ilike(f"%{search}%"))
    if hierarchy_level:
        query = query.where(Location.hierarchy_level == hierarchy_level)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/locations/{location_id}")
async def get_location(location_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific location."""
    query = select(Location).where(Location.id == location_id)
    result = await db.execute(query)
    location = result.scalar_one_or_none()

    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


# --- Events ---

@router.get("/events")
async def list_events(
    search: Optional[str] = None,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    temporal_scale: Optional[str] = None,
    certainty: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List events with optional filters."""
    query = select(Event)

    if search:
        query = query.where(Event.name.ilike(f"%{search}%"))
    if year_start:
        query = query.where(Event.date_start >= year_start)
    if year_end:
        query = query.where(Event.date_start <= year_end)
    if temporal_scale:
        query = query.where(Event.temporal_scale == temporal_scale)
    if certainty:
        query = query.where(Event.certainty == certainty)

    query = query.order_by(Event.date_start).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/events/{event_id}")
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific event."""
    query = select(Event).where(Event.id == event_id)
    result = await db.execute(query)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


# --- Periods ---

@router.get("/periods")
async def list_periods(
    scale: Optional[str] = None,
    parent_id: Optional[int] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List periods with optional filters."""
    query = select(Period)

    if scale:
        query = query.where(Period.scale == scale)
    if parent_id is not None:
        query = query.where(Period.parent_id == parent_id)

    query = query.order_by(Period.year_start).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/periods/{period_id}")
async def get_period(period_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific period."""
    query = select(Period).where(Period.id == period_id)
    result = await db.execute(query)
    period = result.scalar_one_or_none()

    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    return period
