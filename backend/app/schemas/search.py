"""Search schemas."""
from pydantic import BaseModel
from typing import Optional

from app.schemas.event import Event
from app.schemas.person import Person
from app.schemas.location import Location


class SearchResults(BaseModel):
    """Unified search results."""
    query: str
    results: dict[str, list]  # events, persons, locations


class DateLocationQuery(BaseModel):
    """Query for date+location observation."""
    year: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: float = 100


class ObservationResult(BaseModel):
    """
    SHEBA observation result.

    Returns what was happening at a specific point in time/space.
    """
    year: int
    year_display: str
    location: Optional[Location] = None
    events: list[Event] = []
    persons_active: list[Person] = []  # Persons alive at that time
    snapshot_version: Optional[int] = None
