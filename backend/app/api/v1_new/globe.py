"""
Globe API - Markers and connections for 3D globe visualization.

This endpoint provides:
- Location markers filtered by time and space
- Event markers with coordinates
- Person markers (birth/death locations)
- Connections between related entities
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Literal
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db

router = APIRouter(prefix="/globe", tags=["globe"])


# ============== Response Models ==============

class GlobeMarker(BaseModel):
    id: int
    type: Literal["event", "person", "location"]
    lat: float
    lng: float
    year: Optional[int] = None
    year_end: Optional[int] = None
    category: Optional[str] = None
    title: str
    description: Optional[str] = None
    certainty: Optional[str] = None
    color: Optional[str] = None


class GlobeConnection(BaseModel):
    source_id: int
    source_type: str
    target_id: int
    target_type: str
    source_lat: float
    source_lng: float
    target_lat: float
    target_lng: float
    connection_type: str
    year: Optional[int] = None


class MarkerStats(BaseModel):
    total_markers: int
    by_type: dict
    year_range: dict


# ============== Helper Functions ==============

def get_marker_color(entity_type: str, category: str = None, certainty: str = None) -> str:
    """Get marker color based on type and category."""
    if entity_type == "event":
        category_colors = {
            "battle": "#ef4444",      # red
            "war": "#dc2626",         # darker red
            "treaty": "#3b82f6",      # blue
            "discovery": "#22c55e",   # green
            "cultural": "#a855f7",    # purple
            "political": "#f59e0b",   # amber
            "religious": "#8b5cf6",   # violet
        }
        return category_colors.get(category, "#6b7280")  # gray default

    elif entity_type == "person":
        certainty_colors = {
            "fact": "#3b82f6",         # blue
            "probable": "#22c55e",     # green
            "legendary": "#f59e0b",    # amber
            "mythological": "#a855f7", # purple
        }
        return certainty_colors.get(certainty, "#6b7280")

    elif entity_type == "location":
        return "#14b8a6"  # teal

    return "#6b7280"  # gray


# ============== Endpoints ==============

@router.get("/markers", response_model=List[GlobeMarker])
async def get_globe_markers(
    types: str = Query("event,location", description="Comma-separated: event,person,location"),
    year_start: Optional[int] = Query(None, description="Filter from year (BCE as negative)"),
    year_end: Optional[int] = Query(None, description="Filter to year"),
    bounds: Optional[str] = Query(None, description="lat1,lng1,lat2,lng2 bounding box"),
    category: Optional[str] = Query(None, description="Filter by category"),
    certainty: Optional[str] = Query(None, description="Filter by certainty level"),
    limit: int = Query(1000, ge=1, le=5000, description="Max markers to return"),
    db: Session = Depends(get_db),
):
    """
    Get markers for the globe visualization.

    Supports filtering by:
    - Entity types (event, person, location)
    - Time range (year_start to year_end)
    - Spatial bounds (bounding box)
    - Category and certainty level
    """
    type_list = [t.strip() for t in types.split(",")]
    markers = []

    # Parse bounds if provided
    bounds_filter = ""
    bounds_params = {}
    if bounds:
        try:
            lat1, lng1, lat2, lng2 = map(float, bounds.split(","))
            bounds_filter = """
                AND latitude BETWEEN :lat_min AND :lat_max
                AND longitude BETWEEN :lng_min AND :lng_max
            """
            bounds_params = {
                "lat_min": min(lat1, lat2),
                "lat_max": max(lat1, lat2),
                "lng_min": min(lng1, lng2),
                "lng_max": max(lng1, lng2),
            }
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bounds format. Use: lat1,lng1,lat2,lng2")

    # Get event markers (join with locations via primary_location_id)
    if "event" in type_list:
        conditions = ["l.latitude IS NOT NULL", "l.longitude IS NOT NULL"]
        params = {"limit": limit}
        params.update(bounds_params)

        if year_start is not None:
            conditions.append("e.date_start >= :year_start")
            params["year_start"] = year_start
        if year_end is not None:
            conditions.append("e.date_start <= :year_end")
            params["year_end"] = year_end
        if certainty:
            conditions.append("e.certainty = :certainty")
            params["certainty"] = certainty

        # Update bounds filter for joined query
        event_bounds_filter = bounds_filter.replace("latitude", "l.latitude").replace("longitude", "l.longitude")
        where_clause = " AND ".join(conditions) + event_bounds_filter

        result = db.execute(text(f"""
            SELECT e.id, e.title, e.title_ko, e.date_start, e.date_end,
                   l.latitude, l.longitude,
                   e.certainty, e.temporal_scale, e.description
            FROM events e
            JOIN locations l ON e.primary_location_id = l.id
            WHERE {where_clause}
            ORDER BY e.date_start NULLS LAST
            LIMIT :limit
        """), params)

        for row in result:
            markers.append(GlobeMarker(
                id=row[0],
                type="event",
                title=row[1] or "Unknown Event",
                lat=float(row[5]),
                lng=float(row[6]),
                year=row[3],
                year_end=row[4],
                certainty=row[7],
                category=row[8],  # temporal_scale as category for now
                description=row[9],
                color=get_marker_color("event", row[8], row[7])
            ))

    # Get location markers
    if "location" in type_list:
        conditions = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
        params = {"limit": limit}
        params.update(bounds_params)

        if category:
            conditions.append("type = :loc_type")
            params["loc_type"] = category

        where_clause = " AND ".join(conditions) + bounds_filter

        result = db.execute(text(f"""
            SELECT id, name, name_ko, latitude, longitude, type, modern_name
            FROM locations
            WHERE {where_clause}
            LIMIT :limit
        """), params)

        for row in result:
            markers.append(GlobeMarker(
                id=row[0],
                type="location",
                title=row[1] or "Unknown Location",
                lat=float(row[3]),
                lng=float(row[4]),
                category=row[5],
                description=row[6],  # modern_name as description
                color=get_marker_color("location")
            ))

    # Get person markers (birth locations)
    if "person" in type_list:
        conditions = ["p.birth_year IS NOT NULL"]
        params = {"limit": limit}

        if year_start is not None:
            conditions.append("p.birth_year >= :year_start")
            params["year_start"] = year_start
        if year_end is not None:
            conditions.append("p.birth_year <= :year_end")
            params["year_end"] = year_end
        if certainty:
            conditions.append("p.certainty = :certainty")
            params["certainty"] = certainty

        where_clause = " AND ".join(conditions)

        # Join with locations to get coordinates
        # For now, use a simple approach - look for location matches
        result = db.execute(text(f"""
            SELECT p.id, p.name, p.name_ko, p.birth_year, p.death_year,
                   p.role, p.certainty, l.latitude, l.longitude
            FROM persons p
            LEFT JOIN locations l ON LOWER(l.name) LIKE '%' || LOWER(SPLIT_PART(p.name, ' of ', 2)) || '%'
            WHERE {where_clause}
            AND l.latitude IS NOT NULL
            ORDER BY p.mention_count DESC NULLS LAST
            LIMIT :limit
        """), params)

        for row in result:
            if row[7] and row[8]:  # has coordinates
                markers.append(GlobeMarker(
                    id=row[0],
                    type="person",
                    title=row[1] or "Unknown Person",
                    lat=float(row[7]),
                    lng=float(row[8]),
                    year=row[3],
                    year_end=row[4],
                    category=row[5],  # role
                    certainty=row[6],
                    color=get_marker_color("person", None, row[6])
                ))

    return markers[:limit]


@router.get("/markers/stats", response_model=MarkerStats)
async def get_marker_stats(
    year_start: Optional[int] = Query(None),
    year_end: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get statistics about available markers."""
    # Event count with coordinates (join with locations)
    event_params = {}
    event_conditions = ["l.latitude IS NOT NULL", "e.primary_location_id IS NOT NULL"]
    if year_start:
        event_conditions.append("e.date_start >= :year_start")
        event_params["year_start"] = year_start
    if year_end:
        event_conditions.append("e.date_start <= :year_end")
        event_params["year_end"] = year_end

    event_where = " AND ".join(event_conditions)
    event_count = db.execute(
        text(f"""
            SELECT COUNT(*)
            FROM events e
            JOIN locations l ON e.primary_location_id = l.id
            WHERE {event_where}
        """),
        event_params
    ).scalar()

    # Location count with coordinates
    location_count = db.execute(
        text("SELECT COUNT(*) FROM locations WHERE latitude IS NOT NULL")
    ).scalar()

    # Year range
    year_range_result = db.execute(text("""
        SELECT MIN(date_start), MAX(date_start)
        FROM events WHERE date_start IS NOT NULL
    """)).fetchone()

    return MarkerStats(
        total_markers=event_count + location_count,
        by_type={
            "events": event_count,
            "locations": location_count,
        },
        year_range={
            "min": year_range_result[0] if year_range_result else None,
            "max": year_range_result[1] if year_range_result else None,
        }
    )


@router.get("/markers/density")
async def get_marker_density(
    bucket_size: int = Query(100, description="Year bucket size for aggregation"),
    types: str = Query("event", description="Entity types to include"),
    db: Session = Depends(get_db),
):
    """
    Get event density over time for timeline heatmap.
    Returns counts per time bucket.
    """
    type_list = [t.strip() for t in types.split(",")]

    if "event" in type_list:
        result = db.execute(text("""
            SELECT
                FLOOR(e.date_start / :bucket_size) * :bucket_size as year_bucket,
                COUNT(*) as count
            FROM events e
            JOIN locations l ON e.primary_location_id = l.id
            WHERE e.date_start IS NOT NULL AND l.latitude IS NOT NULL
            GROUP BY year_bucket
            ORDER BY year_bucket
        """), {"bucket_size": bucket_size})

        buckets = [{"year": int(row[0]), "count": row[1]} for row in result]

        return {
            "bucket_size": bucket_size,
            "buckets": buckets,
            "total_events": sum(b["count"] for b in buckets)
        }

    return {"bucket_size": bucket_size, "buckets": [], "total_events": 0}


@router.get("/connections/{entity_type}/{entity_id}")
async def get_entity_connections(
    entity_type: str,
    entity_id: int,
    connection_types: Optional[str] = Query(None, description="Filter connection types"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get connections from a specific entity to other entities.
    Useful for visualizing relationships on the globe.
    """
    if entity_type not in ["event", "person", "location"]:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    connections = []

    if entity_type == "event":
        # Get event's location (join with locations)
        event = db.execute(text("""
            SELECT e.id, e.title, l.latitude, l.longitude, e.date_start
            FROM events e
            JOIN locations l ON e.primary_location_id = l.id
            WHERE e.id = :id
        """), {"id": entity_id}).fetchone()

        if not event or not event[2]:
            return {"entity_id": entity_id, "entity_type": entity_type, "connections": []}

        # Find other events at the same location or same time period
        result = db.execute(text("""
            SELECT e.id, e.title, l.latitude, l.longitude, e.date_start
            FROM events e
            JOIN locations l ON e.primary_location_id = l.id
            WHERE e.id != :id
            AND l.latitude IS NOT NULL
            AND (
                -- Same location (within ~100km)
                (ABS(l.latitude - :lat) < 1 AND ABS(l.longitude - :lng) < 1)
                OR
                -- Same time period (within 50 years)
                (e.date_start IS NOT NULL AND ABS(e.date_start - :year) < 50)
            )
            LIMIT :limit
        """), {
            "id": entity_id,
            "lat": event[2],
            "lng": event[3],
            "year": event[4] or 0,
            "limit": limit
        })

        for row in result:
            connections.append(GlobeConnection(
                source_id=entity_id,
                source_type="event",
                target_id=row[0],
                target_type="event",
                source_lat=float(event[2]),
                source_lng=float(event[3]),
                target_lat=float(row[2]),
                target_lng=float(row[3]),
                connection_type="temporal" if abs((row[4] or 0) - (event[4] or 0)) < 50 else "spatial",
                year=row[4]
            ))

    elif entity_type == "location":
        # Get events at this location
        location = db.execute(text("""
            SELECT id, name, latitude, longitude
            FROM locations WHERE id = :id
        """), {"id": entity_id}).fetchone()

        if not location or not location[2]:
            return {"entity_id": entity_id, "entity_type": entity_type, "connections": []}

        # Find events near this location (join with locations)
        result = db.execute(text("""
            SELECT e.id, e.title, l.latitude, l.longitude, e.date_start
            FROM events e
            JOIN locations l ON e.primary_location_id = l.id
            WHERE l.latitude IS NOT NULL
            AND ABS(l.latitude - :lat) < 0.5 AND ABS(l.longitude - :lng) < 0.5
            ORDER BY e.date_start NULLS LAST
            LIMIT :limit
        """), {
            "lat": location[2],
            "lng": location[3],
            "limit": limit
        })

        for row in result:
            connections.append(GlobeConnection(
                source_id=entity_id,
                source_type="location",
                target_id=row[0],
                target_type="event",
                source_lat=float(location[2]),
                source_lng=float(location[3]),
                target_lat=float(row[2]),
                target_lng=float(row[3]),
                connection_type="location_event",
                year=row[4]
            ))

    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "connections": connections
    }


class GlobeArc(BaseModel):
    """Arc data for Historical Chain visualization on globe."""
    connection_id: int
    source_event_id: int
    target_event_id: int
    source_title: str
    target_title: str
    source_lat: float
    source_lng: float
    target_lat: float
    target_lng: float
    source_year: Optional[int] = None
    target_year: Optional[int] = None
    layer_type: str  # person, location, causal, thematic
    connection_type: Optional[str] = None  # causes, leads_to, follows, etc.
    direction: str  # forward, backward, bidirectional
    strength: float


@router.get("/arcs/{event_id}", response_model=List[GlobeArc])
async def get_event_arcs(
    event_id: int,
    layer_type: Optional[str] = Query(None, description="Filter by layer: person, location, causal"),
    min_strength: float = Query(3.0, description="Minimum connection strength"),
    limit: int = Query(30, ge=1, le=100, description="Max arcs to return"),
    db: Session = Depends(get_db),
):
    """
    Get arc data for Historical Chain visualization on globe.
    Returns connections with coordinates for drawing arcs between events.
    """
    arcs = []

    # Build conditions
    conditions = ["(ec.event_a_id = :event_id OR ec.event_b_id = :event_id)"]
    params = {"event_id": event_id, "min_strength": min_strength, "limit": limit}

    conditions.append("ec.strength_score >= :min_strength")

    if layer_type:
        conditions.append("ec.layer_type = :layer_type")
        params["layer_type"] = layer_type

    where_clause = " AND ".join(conditions)

    # Query connections with coordinates
    result = db.execute(text(f"""
        SELECT
            ec.id,
            ec.event_a_id,
            ec.event_b_id,
            ea.title as title_a,
            eb.title as title_b,
            la.latitude as lat_a,
            la.longitude as lng_a,
            lb.latitude as lat_b,
            lb.longitude as lng_b,
            ea.date_start as year_a,
            eb.date_start as year_b,
            ec.layer_type,
            ec.connection_type,
            ec.direction,
            ec.strength_score
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        LEFT JOIN locations la ON ea.primary_location_id = la.id
        LEFT JOIN locations lb ON eb.primary_location_id = lb.id
        WHERE {where_clause}
          AND la.latitude IS NOT NULL
          AND lb.latitude IS NOT NULL
        ORDER BY ec.strength_score DESC
        LIMIT :limit
    """), params)

    for row in result:
        # Determine source/target based on which event was selected
        if row[1] == event_id:
            # event_a is source
            arcs.append(GlobeArc(
                connection_id=row[0],
                source_event_id=row[1],
                target_event_id=row[2],
                source_title=row[3],
                target_title=row[4],
                source_lat=float(row[5]),
                source_lng=float(row[6]),
                target_lat=float(row[7]),
                target_lng=float(row[8]),
                source_year=row[9],
                target_year=row[10],
                layer_type=row[11],
                connection_type=row[12],
                direction=row[13],
                strength=float(row[14])
            ))
        else:
            # event_b is source (flip the arc)
            arcs.append(GlobeArc(
                connection_id=row[0],
                source_event_id=row[2],
                target_event_id=row[1],
                source_title=row[4],
                target_title=row[3],
                source_lat=float(row[7]),
                source_lng=float(row[8]),
                target_lat=float(row[5]),
                target_lng=float(row[6]),
                source_year=row[10],
                target_year=row[9],
                layer_type=row[11],
                connection_type=row[12],
                direction=row[13],
                strength=float(row[14])
            ))

    return arcs


@router.get("/clusters")
async def get_marker_clusters(
    year_start: Optional[int] = Query(None),
    year_end: Optional[int] = Query(None),
    grid_size: float = Query(5.0, description="Grid cell size in degrees"),
    db: Session = Depends(get_db),
):
    """
    Get clustered markers for zoomed-out view.
    Groups markers by geographic grid cells.
    """
    params = {"grid_size": grid_size}
    conditions = ["l.latitude IS NOT NULL"]

    if year_start:
        conditions.append("e.date_start >= :year_start")
        params["year_start"] = year_start
    if year_end:
        conditions.append("e.date_start <= :year_end")
        params["year_end"] = year_end

    where_clause = " AND ".join(conditions)

    result = db.execute(text(f"""
        SELECT
            FLOOR(l.latitude / :grid_size) * :grid_size + :grid_size / 2 as center_lat,
            FLOOR(l.longitude / :grid_size) * :grid_size + :grid_size / 2 as center_lng,
            COUNT(*) as count,
            MIN(e.date_start) as min_year,
            MAX(e.date_start) as max_year
        FROM events e
        JOIN locations l ON e.primary_location_id = l.id
        WHERE {where_clause}
        GROUP BY FLOOR(l.latitude / :grid_size), FLOOR(l.longitude / :grid_size)
        HAVING COUNT(*) > 0
        ORDER BY count DESC
    """), params)

    clusters = [
        {
            "lat": float(row[0]),
            "lng": float(row[1]),
            "count": row[2],
            "year_range": [row[3], row[4]]
        }
        for row in result
    ]

    return {
        "grid_size": grid_size,
        "clusters": clusters,
        "total_clusters": len(clusters)
    }
