"""
Period schemas for API validation.
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# Braudel's temporal scales
TemporalScale = Literal["evenementielle", "conjuncture", "longue_duree"]


class PeriodBase(BaseModel):
    """Base schema with common fields."""
    name: str = Field(..., min_length=1, max_length=200)
    name_ko: Optional[str] = Field(None, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    year_start: int = Field(..., description="Start year (negative for BCE)")
    year_end: Optional[int] = Field(None, description="End year (negative for BCE, null for ongoing)")
    scale: TemporalScale = Field(default="conjuncture")
    parent_id: Optional[int] = None
    description: Optional[str] = None
    description_ko: Optional[str] = None
    is_manual: bool = True


class PeriodCreate(PeriodBase):
    """Schema for creating a new period."""
    pass


class PeriodUpdate(BaseModel):
    """Schema for updating a period (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    name_ko: Optional[str] = Field(None, max_length=200)
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    scale: Optional[TemporalScale] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    description_ko: Optional[str] = None
    is_manual: Optional[bool] = None


class Period(PeriodBase):
    """Schema for reading a period."""
    id: int
    year_display: Optional[str] = None
    duration_years: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PeriodWithChildren(Period):
    """Period with nested children for hierarchical display."""
    children: List["PeriodWithChildren"] = []


class PeriodList(BaseModel):
    """Paginated list of periods."""
    items: List[Period]
    total: int
    page: int
    size: int
    pages: int


# Enable forward reference resolution
PeriodWithChildren.model_rebuild()
