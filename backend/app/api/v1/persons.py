"""
Persons API endpoints.

Provides CRUD operations for historical figures.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.person import Person, PersonList, PersonDetail, PersonRelation, PersonRelationList
from app.services import person_service

router = APIRouter()


@router.get("", response_model=PersonList)
async def list_persons(
    year_start: Optional[int] = Query(None, description="Active from year"),
    year_end: Optional[int] = Query(None, description="Active until year"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    include_orphans: bool = Query(False, description="Include entities with no connections"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List historical figures with optional filtering.

    By default, excludes orphan entities (those with no relationships).
    Set include_orphans=true to see all entities.
    """
    persons, total = person_service.get_persons(
        db,
        year_start=year_start,
        year_end=year_end,
        category_id=category_id,
        limit=limit,
        offset=offset,
        include_orphans=include_orphans,
    )
    return PersonList(items=persons, total=total)


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    person_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information about a historical figure."""
    person = person_service.get_person_by_id(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.get("/{person_id}/events")
async def get_person_events(
    person_id: int,
    db: Session = Depends(get_db),
):
    """Get events associated with a person."""
    events = person_service.get_person_events(db, person_id)
    return {"person_id": person_id, "events": events}


@router.get("/{person_id}/relations", response_model=PersonRelationList)
async def get_person_relations(
    person_id: int,
    limit: int = Query(20, ge=1, le=100, description="Max relations to return"),
    min_strength: float = Query(0, ge=0, description="Minimum strength threshold"),
    db: Session = Depends(get_db),
):
    """
    Get related persons with relationship strength.

    Returns persons connected to this person via person_relationships table,
    sorted by strength descending.

    - strength: Relationship strength (higher = stronger connection)
    - time_distance: Years between persons (null = contemporary, positive = apart)
    - relationship_type: Type of relationship (wikipedia_link, content_mention, etc.)
    """
    relations = person_service.get_related_persons(
        db,
        person_id=person_id,
        limit=limit,
        min_strength=min_strength,
    )
    return PersonRelationList(
        person_id=person_id,
        relations=[PersonRelation(**r) for r in relations],
        total=len(relations),
    )
