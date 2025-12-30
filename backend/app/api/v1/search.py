"""
Search API endpoints.

Provides unified search across events, persons, and locations.
Also supports date+location queries for temporal-spatial exploration.
"""
from fastapi import APIRouter, Query
from typing import Optional

from app.services.json_data import get_data_service

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Unified search across all data types.

    Searches titles, names, descriptions.
    """
    data_service = get_data_service()
    results = data_service.search(q, limit=limit)
    return {
        "query": q,
        "events": results["events"],
        "locations": results["locations"],
        "persons": results["persons"],
        "total": (
            len(results["events"]) +
            len(results["locations"]) +
            len(results["persons"])
        ),
    }


@router.get("/date-location")
async def search_by_date_location(
    year: int = Query(..., description="Year to observe (negative for BCE)"),
    latitude: Optional[float] = Query(None, ge=-90, le=90),
    longitude: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(100, ge=1, le=5000),
    year_range: int = Query(10, ge=1, le=100),
):
    """
    Observe a specific point in time and space.

    This is the core SHEBA observation function:
    - Given a year and optional location
    - Returns events that occurred then/there

    Example: year=-490, lat=38.15, lng=23.96 -> Battle of Marathon
    """
    data_service = get_data_service()

    # Get events near the year
    events = data_service.get_events(
        year_start=year - year_range,
        year_end=year + year_range,
        limit=100,
    )

    # Filter by location if provided
    if latitude is not None and longitude is not None:
        import math

        def distance_km(lat1, lon1, lat2, lon2):
            """Haversine distance."""
            R = 6371  # Earth radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2 +
                math.cos(math.radians(lat1)) *
                math.cos(math.radians(lat2)) *
                math.sin(dlon / 2) ** 2
            )
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        events = [
            e for e in events
            if e.get("latitude") and e.get("longitude")
            and distance_km(latitude, longitude, e["latitude"], e["longitude"]) <= radius_km
        ]

    return {
        "year": year,
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "events": events,
        "count": len(events),
    }
