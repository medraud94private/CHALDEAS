"""Event schemas."""
from pydantic import BaseModel
from typing import Optional

from app.schemas.category import Category
from app.schemas.location import Location
from app.schemas.source import Source


class EventBase(BaseModel):
    title: str
    title_ko: Optional[str] = None
    date_start: int  # Negative for BCE
    date_end: Optional[int] = None
    date_display: str
    importance: int = 3


class Event(EventBase):
    """Event for list/globe view."""
    id: int
    category: Optional[Category] = None
    location: Optional[Location] = None  # Primary location

    class Config:
        from_attributes = True


class PersonBrief(BaseModel):
    """Brief person info for event detail."""
    id: int
    name: str
    name_ko: Optional[str] = None
    role: Optional[str] = None

    class Config:
        from_attributes = True


class EventDetail(Event):
    """Full event details for wiki panel."""
    slug: str
    description: Optional[str] = None
    description_ko: Optional[str] = None
    date_precision: str = "year"
    date_start_month: Optional[int] = None
    date_start_day: Optional[int] = None
    date_end_month: Optional[int] = None
    date_end_day: Optional[int] = None
    locations: list[Location] = []
    persons: list[PersonBrief] = []
    sources: list[Source] = []
    image_url: Optional[str] = None
    wikipedia_url: Optional[str] = None


class EventList(BaseModel):
    items: list[Event]
    total: int
