"""
Chain API Endpoints
Historical Chain CRUD and curation queries
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import HistoricalChain, ChainSegment
from app.schemas.chain import (
    ChainCreate, ChainResponse, ChainWithSegments,
    CurationRequest, CurationResponse
)
from app.services.chain_generator import ChainGenerator

router = APIRouter()


@router.get("/", response_model=List[ChainResponse])
async def list_chains(
    chain_type: Optional[str] = None,
    visibility: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List all historical chains with optional filters."""
    query = select(HistoricalChain)

    if chain_type:
        query = query.where(HistoricalChain.chain_type == chain_type)
    if visibility:
        query = query.where(HistoricalChain.visibility == visibility)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    chains = result.scalars().all()

    return chains


@router.get("/{chain_id}", response_model=ChainWithSegments)
async def get_chain(
    chain_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chain with all segments."""
    query = select(HistoricalChain).options(
        selectinload(HistoricalChain.segments)
    ).where(HistoricalChain.id == chain_id)

    result = await db.execute(query)
    chain = result.scalar_one_or_none()

    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")

    # Increment access count
    chain.increment_access()
    await db.commit()

    return chain


@router.post("/curate", response_model=CurationResponse)
async def curate_chain(
    request: CurationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate or retrieve a curated historical chain.

    Chain types:
    - person_story: Life story of a historical figure
    - place_story: History of a location over time
    - era_story: Overview of a period with key events
    - causal_chain: Cause-and-effect sequence of events
    """
    generator = ChainGenerator(db)

    # Check for existing cached chain
    existing = await generator.find_cached_chain(request)
    if existing:
        existing.increment_access()
        await db.commit()
        return CurationResponse(
            chain=existing,
            cached=True,
            message="Retrieved from cache"
        )

    # Generate new chain
    try:
        chain = await generator.generate_chain(request)
        db.add(chain)
        await db.commit()

        # Reload with segments eagerly loaded
        query = select(HistoricalChain).options(
            selectinload(HistoricalChain.segments)
        ).where(HistoricalChain.id == chain.id)
        result = await db.execute(query)
        chain_with_segments = result.scalar_one()

        return CurationResponse(
            chain=chain_with_segments,
            cached=False,
            message="Generated new chain"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ChainResponse)
async def create_chain(
    chain_data: ChainCreate,
    db: AsyncSession = Depends(get_db)
):
    """Manually create a historical chain."""
    chain = HistoricalChain(**chain_data.model_dump())
    db.add(chain)
    await db.commit()
    await db.refresh(chain)
    return chain


@router.delete("/{chain_id}")
async def delete_chain(
    chain_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a chain (only user-level visibility)."""
    query = select(HistoricalChain).where(HistoricalChain.id == chain_id)
    result = await db.execute(query)
    chain = result.scalar_one_or_none()

    if not chain:
        raise HTTPException(status_code=404, detail="Chain not found")

    if chain.visibility != "user":
        raise HTTPException(
            status_code=403,
            detail="Cannot delete cached/featured/system chains"
        )

    await db.delete(chain)
    await db.commit()
    return {"message": "Chain deleted"}
