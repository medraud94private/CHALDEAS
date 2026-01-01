"""
Chain Pydantic Schemas
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# --- Chain Segment ---

class SegmentBase(BaseModel):
    segment_order: int
    event_id: int
    narrative: Optional[str] = None
    narrative_ko: Optional[str] = None
    connection_type: Optional[str] = None


class SegmentCreate(SegmentBase):
    pass


class SegmentResponse(SegmentBase):
    id: int
    chain_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Historical Chain ---

class ChainBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    title_ko: Optional[str] = None
    description: Optional[str] = None
    chain_type: Literal["person_story", "place_story", "era_story", "causal_chain"]
    person_id: Optional[int] = None
    location_id: Optional[int] = None
    period_id: Optional[int] = None


class ChainCreate(ChainBase):
    pass


class ChainResponse(ChainBase):
    id: int
    visibility: str
    access_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChainWithSegments(ChainResponse):
    segments: List[SegmentResponse] = []


# --- Curation Request/Response ---

class CurationRequest(BaseModel):
    """Request for generating/retrieving a historical chain."""
    chain_type: Literal["person_story", "place_story", "era_story", "causal_chain"]

    # Entity ID based on chain_type
    person_id: Optional[int] = None
    location_id: Optional[int] = None
    period_id: Optional[int] = None

    # Optional time range
    year_start: Optional[int] = None
    year_end: Optional[int] = None

    # Options
    max_segments: int = Field(default=5, ge=1, le=50)
    language: str = Field(default="en")


class CurationResponse(BaseModel):
    """Response containing the curated chain."""
    chain: ChainWithSegments
    cached: bool
    message: str
