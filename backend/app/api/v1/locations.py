"""
Locations API endpoints.

Provides access to geographical locations from Pleiades and Wikidata.
"""
from fastapi import APIRouter, Query
from typing import Optional

from app.services.json_data import get_data_service

router = APIRouter()


@router.get("")
async def list_locations(
    lat_min: Optional[float] = Query(None, description="Minimum latitude"),
    lat_max: Optional[float] = Query(None, description="Maximum latitude"),
    lng_min: Optional[float] = Query(None, description="Minimum longitude"),
    lng_max: Optional[float] = Query(None, description="Maximum longitude"),
    limit: int = Query(100, ge=1, le=10000),
):
    """
    List locations with optional bounding box filtering.

    Returns locations from Pleiades and Wikidata sources.
    """
    data_service = get_data_service()
    locations = data_service.get_locations(
        lat_min=lat_min,
        lat_max=lat_max,
        lng_min=lng_min,
        lng_max=lng_max,
        limit=limit,
    )
    return {
        "items": locations,
        "total": len(data_service.locations),
        "filtered": len(locations),
    }


@router.get("/stats")
async def get_location_stats():
    """Get statistics about location data."""
    data_service = get_data_service()
    locations = data_service.locations

    # Count by source
    pleiades_count = sum(1 for l in locations if l.get("source") == "pleiades")
    wikidata_count = sum(1 for l in locations if l.get("source") == "wikidata")

    return {
        "total": len(locations),
        "pleiades": pleiades_count,
        "wikidata": wikidata_count,
    }


@router.get("/{location_id}")
async def get_location(location_id: str):
    """Get detailed information about a specific location."""
    data_service = get_data_service()
    for location in data_service.locations:
        if location.get("id") == location_id:
            return location
    return {"error": "Location not found"}
