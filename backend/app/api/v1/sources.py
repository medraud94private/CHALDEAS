"""
Sources API endpoints.

Provides:
- List sources (books, documents)
- Source details
- Persons mentioned in a source
- Mentions with context
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.source import (
    SourceList,
    SourceSummary,
    SourceDetail,
    SourcePersonList,
    SourcePersonSummary,
)
from app.services import source_service

router = APIRouter()


@router.get("", response_model=SourceList)
async def list_sources(
    type: Optional[str] = Query(None, description="Filter by type (gutenberg, wikipedia, etc.)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List sources (books, documents) with mention statistics.

    Sources are ordered by total mention count.
    Only sources with at least one text mention are returned.

    Types:
    - gutenberg: Project Gutenberg books
    - wikipedia: Wikipedia articles
    - document: General documents
    - digital_archive: Digital archive entries
    """
    items, total = source_service.get_sources(
        db,
        source_type=type,
        limit=limit,
        offset=offset,
    )

    return SourceList(
        items=[SourceSummary(**item) for item in items],
        total=total
    )


@router.get("/{source_id}", response_model=SourceDetail)
async def get_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a source.

    Includes:
    - Basic metadata (title, author, year)
    - Mention statistics by entity type
    """
    source = source_service.get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return SourceDetail(**source)


@router.get("/{source_id}/persons", response_model=SourcePersonList)
async def get_source_persons(
    source_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_mentions: int = Query(1, ge=1, description="Minimum mention count to include"),
    db: Session = Depends(get_db),
):
    """
    Get historical figures mentioned in a source.

    Returns persons ordered by mention count.
    Use min_mentions to filter out minor mentions.
    """
    # Verify source exists
    source = source_service.get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    persons, total = source_service.get_source_persons(
        db,
        source_id=source_id,
        limit=limit,
        offset=offset,
        min_mentions=min_mentions,
    )

    return SourcePersonList(
        source_id=source_id,
        persons=[SourcePersonSummary(**p) for p in persons],
        total=total
    )


@router.get("/{source_id}/mentions")
async def get_source_mentions(
    source_id: int,
    entity_type: Optional[str] = Query(None, description="Filter by entity type (person, location, event)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get all entity mentions in a source with context.

    Returns mentions ordered by position in document (chunk_index).
    Includes the actual mention text and surrounding context.
    """
    # Verify source exists
    source = source_service.get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    mentions, total = source_service.get_source_mentions(
        db,
        source_id=source_id,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )

    return {
        "source_id": source_id,
        "mentions": mentions,
        "total": total
    }
