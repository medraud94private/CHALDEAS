"""
Search service - Unified search and SHEBA observation.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from math import radians, cos, sin, asin, sqrt

from app.models.event import Event
from app.models.person import Person
from app.models.location import Location
from app.schemas.search import SearchResults, ObservationResult


def search_all(
    db: Session,
    query: str,
    type_filter: Optional[str] = None,
    limit: int = 20,
) -> SearchResults:
    """
    Unified search across events, persons, and locations.
    """
    results = {"events": [], "persons": [], "locations": []}
    search_term = f"%{query}%"

    if type_filter in (None, "all", "event"):
        events = db.query(Event).filter(
            or_(
                Event.title.ilike(search_term),
                Event.title_ko.ilike(search_term),
                Event.description.ilike(search_term),
            )
        ).limit(limit).all()
        results["events"] = events

    if type_filter in (None, "all", "person"):
        persons = db.query(Person).filter(
            or_(
                Person.name.ilike(search_term),
                Person.name_ko.ilike(search_term),
                Person.biography.ilike(search_term),
            )
        ).limit(limit).all()
        results["persons"] = persons

    if type_filter in (None, "all", "location"):
        locations = db.query(Location).filter(
            or_(
                Location.name.ilike(search_term),
                Location.name_ko.ilike(search_term),
                Location.modern_name.ilike(search_term),
            )
        ).limit(limit).all()
        results["locations"] = locations

    return SearchResults(query=query, results=results)


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great circle distance in km between two points."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c  # Earth radius in km


def observe_date_location(
    db: Session,
    year: int,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: float = 100,
) -> ObservationResult:
    """
    SHEBA core observation function.

    Given a year and optional location, returns:
    - Events that occurred at that time/place
    - Persons who were alive then
    """
    # Format year display
    abs_year = abs(year)
    era = "BCE" if year < 0 else "CE"
    year_display = f"{abs_year} {era}"

    # Find events in that year
    events_query = db.query(Event).filter(
        Event.date_start <= year,
        or_(
            Event.date_end >= year,
            Event.date_end.is_(None)
        )
    )

    events = events_query.all()

    # Filter by location if provided
    if latitude is not None and longitude is not None:
        events = [
            e for e in events
            if e.primary_location and haversine(
                longitude, latitude,
                float(e.primary_location.longitude),
                float(e.primary_location.latitude)
            ) <= radius_km
        ]

    # Find persons alive in that year
    persons = db.query(Person).filter(
        Person.birth_year <= year,
        or_(
            Person.death_year >= year,
            Person.death_year.is_(None)
        )
    ).all()

    return ObservationResult(
        year=year,
        year_display=year_display,
        events=events,
        persons_active=persons,
    )
