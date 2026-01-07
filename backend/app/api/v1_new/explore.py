"""
Explore API - Browse raw NER-extracted entities before curation.

This endpoint provides access to the pre-curation entity pool:
- Browse persons, locations, events, polities, periods
- Filter by confidence, era, certainty
- Search by name
- Statistics and summaries
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db

router = APIRouter(prefix="/explore", tags=["explore"])


# Pydantic models for responses
class EntitySummary(BaseModel):
    id: int
    name: str
    name_ko: Optional[str] = None
    slug: Optional[str] = None

    class Config:
        from_attributes = True


class PersonExplore(EntitySummary):
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    role: Optional[str] = None
    era: Optional[str] = None
    certainty: Optional[str] = None
    mention_count: Optional[int] = None
    avg_confidence: Optional[float] = None


class LocationExplore(EntitySummary):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    type: Optional[str] = None
    modern_name: Optional[str] = None
    country: Optional[str] = None


class EventExplore(EntitySummary):
    title: str
    date_start: Optional[int] = None
    date_end: Optional[int] = None
    certainty: Optional[str] = None
    temporal_scale: Optional[str] = None


class PolityExplore(EntitySummary):
    polity_type: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    certainty: Optional[str] = None


class PeriodExplore(EntitySummary):
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    scale: Optional[str] = None
    parent_id: Optional[int] = None


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


class ExploreStats(BaseModel):
    total_persons: int
    total_locations: int
    total_events: int
    total_polities: int
    total_periods: int
    persons_by_era: dict
    persons_by_certainty: dict
    locations_by_type: dict
    last_updated: str


@router.get("/stats", response_model=ExploreStats)
async def get_explore_stats(db: Session = Depends(get_db)):
    """Get statistics about the entity pool."""
    # Total counts
    total_persons = db.execute(text("SELECT COUNT(*) FROM persons")).scalar()
    total_locations = db.execute(text("SELECT COUNT(*) FROM locations")).scalar()
    total_events = db.execute(text("SELECT COUNT(*) FROM events")).scalar()
    total_polities = db.execute(text("SELECT COUNT(*) FROM polities")).scalar()
    total_periods = db.execute(text("SELECT COUNT(*) FROM periods")).scalar()

    # Persons by era
    era_result = db.execute(text("""
        SELECT COALESCE(era, 'Unknown') as era, COUNT(*) as count
        FROM persons
        GROUP BY era
        ORDER BY count DESC
        LIMIT 10
    """))
    persons_by_era = {row[0]: row[1] for row in era_result}

    # Persons by certainty
    certainty_result = db.execute(text("""
        SELECT COALESCE(certainty, 'unknown') as certainty, COUNT(*) as count
        FROM persons
        GROUP BY certainty
    """))
    persons_by_certainty = {row[0]: row[1] for row in certainty_result}

    # Locations by type
    loc_type_result = db.execute(text("""
        SELECT COALESCE(type, 'unknown') as type, COUNT(*) as count
        FROM locations
        GROUP BY type
        ORDER BY count DESC
        LIMIT 10
    """))
    locations_by_type = {row[0]: row[1] for row in loc_type_result}

    return ExploreStats(
        total_persons=total_persons,
        total_locations=total_locations,
        total_events=total_events,
        total_polities=total_polities,
        total_periods=total_periods,
        persons_by_era=persons_by_era,
        persons_by_certainty=persons_by_certainty,
        locations_by_type=locations_by_type,
        last_updated=datetime.now().isoformat()
    )


@router.get("/persons", response_model=PaginatedResponse)
async def explore_persons(
    q: Optional[str] = Query(None, description="Search by name"),
    era: Optional[str] = Query(None, description="Filter by era"),
    certainty: Optional[str] = Query(None, description="Filter by certainty: fact, probable, legendary, mythological"),
    min_mentions: Optional[int] = Query(None, description="Minimum mention count"),
    year_start: Optional[int] = Query(None, description="Birth year from"),
    year_end: Optional[int] = Query(None, description="Birth year to"),
    sort_by: str = Query("mention_count", description="Sort field: name, mention_count, birth_year"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse extracted persons with filters."""
    # Build query
    conditions = []
    params = {}

    if q:
        conditions.append("name ILIKE :q")
        params["q"] = f"%{q}%"
    if era:
        conditions.append("era = :era")
        params["era"] = era
    if certainty:
        conditions.append("certainty = :certainty")
        params["certainty"] = certainty
    if min_mentions:
        conditions.append("mention_count >= :min_mentions")
        params["min_mentions"] = min_mentions
    if year_start:
        conditions.append("birth_year >= :year_start")
        params["year_start"] = year_start
    if year_end:
        conditions.append("birth_year <= :year_end")
        params["year_end"] = year_end

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Validate sort field
    allowed_sorts = ["name", "mention_count", "birth_year", "death_year", "avg_confidence"]
    if sort_by not in allowed_sorts:
        sort_by = "mention_count"
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    # Count total
    count_sql = f"SELECT COUNT(*) FROM persons WHERE {where_clause}"
    total = db.execute(text(count_sql), params).scalar()

    # Fetch items
    query_sql = f"""
        SELECT id, name, name_ko, slug, birth_year, death_year, role, era,
               certainty, mention_count, avg_confidence
        FROM persons
        WHERE {where_clause}
        ORDER BY {sort_by} {sort_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query_sql), params)
    items = [
        PersonExplore(
            id=row[0], name=row[1], name_ko=row[2], slug=row[3],
            birth_year=row[4], death_year=row[5], role=row[6], era=row[7],
            certainty=row[8], mention_count=row[9], avg_confidence=row[10]
        )
        for row in result
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/locations", response_model=PaginatedResponse)
async def explore_locations(
    q: Optional[str] = Query(None, description="Search by name"),
    type: Optional[str] = Query(None, description="Location type: city, region, country"),
    country: Optional[str] = Query(None, description="Filter by country"),
    has_coordinates: Optional[bool] = Query(None, description="Has lat/lon"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse extracted locations with filters."""
    conditions = []
    params = {}

    if q:
        conditions.append("name ILIKE :q")
        params["q"] = f"%{q}%"
    if type:
        conditions.append("type = :type")
        params["type"] = type
    if country:
        conditions.append("country = :country")
        params["country"] = country
    if has_coordinates is not None:
        if has_coordinates:
            conditions.append("latitude IS NOT NULL AND longitude IS NOT NULL")
        else:
            conditions.append("latitude IS NULL OR longitude IS NULL")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Count
    total = db.execute(text(f"SELECT COUNT(*) FROM locations WHERE {where_clause}"), params).scalar()

    # Fetch
    query_sql = f"""
        SELECT id, name, name_ko, latitude, longitude, type, modern_name, country
        FROM locations
        WHERE {where_clause}
        ORDER BY name
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query_sql), params)
    items = [
        LocationExplore(
            id=row[0], name=row[1], name_ko=row[2],
            latitude=float(row[3]) if row[3] else None,
            longitude=float(row[4]) if row[4] else None,
            type=row[5], modern_name=row[6], country=row[7]
        )
        for row in result
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/events", response_model=PaginatedResponse)
async def explore_events(
    q: Optional[str] = Query(None, description="Search by title"),
    certainty: Optional[str] = Query(None, description="Filter by certainty"),
    year_start: Optional[int] = Query(None, description="Event year from"),
    year_end: Optional[int] = Query(None, description="Event year to"),
    temporal_scale: Optional[str] = Query(None, description="evenementielle, conjuncture, longue_duree"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse extracted events with filters."""
    conditions = []
    params = {}

    if q:
        conditions.append("title ILIKE :q")
        params["q"] = f"%{q}%"
    if certainty:
        conditions.append("certainty = :certainty")
        params["certainty"] = certainty
    if year_start:
        conditions.append("date_start >= :year_start")
        params["year_start"] = year_start
    if year_end:
        conditions.append("date_start <= :year_end")
        params["year_end"] = year_end
    if temporal_scale:
        conditions.append("temporal_scale = :temporal_scale")
        params["temporal_scale"] = temporal_scale

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    total = db.execute(text(f"SELECT COUNT(*) FROM events WHERE {where_clause}"), params).scalar()

    query_sql = f"""
        SELECT id, title, title_ko, slug, date_start, date_end, certainty, temporal_scale
        FROM events
        WHERE {where_clause}
        ORDER BY date_start NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query_sql), params)
    items = [
        EventExplore(
            id=row[0], name=row[1], title=row[1], name_ko=row[2], slug=row[3],
            date_start=row[4], date_end=row[5], certainty=row[6], temporal_scale=row[7]
        )
        for row in result
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/polities", response_model=PaginatedResponse)
async def explore_polities(
    q: Optional[str] = Query(None, description="Search by name"),
    polity_type: Optional[str] = Query(None, description="empire, kingdom, republic, dynasty"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse extracted polities with filters."""
    conditions = []
    params = {}

    if q:
        conditions.append("name ILIKE :q")
        params["q"] = f"%{q}%"
    if polity_type:
        conditions.append("polity_type = :polity_type")
        params["polity_type"] = polity_type

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    total = db.execute(text(f"SELECT COUNT(*) FROM polities WHERE {where_clause}"), params).scalar()

    query_sql = f"""
        SELECT id, name, name_ko, slug, polity_type, start_year, end_year, certainty
        FROM polities
        WHERE {where_clause}
        ORDER BY name
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query_sql), params)
    items = [
        PolityExplore(
            id=row[0], name=row[1], name_ko=row[2], slug=row[3],
            polity_type=row[4], start_year=row[5], end_year=row[6], certainty=row[7]
        )
        for row in result
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/periods", response_model=PaginatedResponse)
async def explore_periods(
    q: Optional[str] = Query(None, description="Search by name"),
    scale: Optional[str] = Query(None, description="evenementielle, conjuncture, longue_duree"),
    parent_id: Optional[int] = Query(None, description="Filter by parent period"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse periods with filters."""
    conditions = []
    params = {}

    if q:
        conditions.append("name ILIKE :q")
        params["q"] = f"%{q}%"
    if scale:
        conditions.append("scale = :scale")
        params["scale"] = scale
    if parent_id:
        conditions.append("parent_id = :parent_id")
        params["parent_id"] = parent_id

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    total = db.execute(text(f"SELECT COUNT(*) FROM periods WHERE {where_clause}"), params).scalar()

    query_sql = f"""
        SELECT id, name, name_ko, slug, year_start, year_end, scale, parent_id
        FROM periods
        WHERE {where_clause}
        ORDER BY year_start NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query_sql), params)
    items = [
        PeriodExplore(
            id=row[0], name=row[1], name_ko=row[2], slug=row[3],
            year_start=row[4], year_end=row[5], scale=row[6], parent_id=row[7]
        )
        for row in result
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/top-mentioned")
async def get_top_mentioned(
    entity_type: str = Query("persons", description="persons, locations"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get top mentioned entities."""
    if entity_type == "persons":
        result = db.execute(text("""
            SELECT id, name, role, era, mention_count, avg_confidence
            FROM persons
            WHERE mention_count IS NOT NULL
            ORDER BY mention_count DESC
            LIMIT :limit
        """), {"limit": limit})

        return {
            "entity_type": "persons",
            "items": [
                {
                    "id": row[0], "name": row[1], "role": row[2],
                    "era": row[3], "mention_count": row[4], "avg_confidence": row[5]
                }
                for row in result
            ]
        }

    elif entity_type == "locations":
        # Locations don't have mention_count, so return by name frequency
        result = db.execute(text("""
            SELECT id, name, type, modern_name, country
            FROM locations
            ORDER BY name
            LIMIT :limit
        """), {"limit": limit})

        return {
            "entity_type": "locations",
            "items": [
                {"id": row[0], "name": row[1], "type": row[2], "modern_name": row[3], "country": row[4]}
                for row in result
            ]
        }

    raise HTTPException(status_code=400, detail="Invalid entity_type")


# ============== Source & Mention Endpoints ==============

class SourceSummary(BaseModel):
    id: int
    name: str
    title: Optional[str] = None
    author: Optional[str] = None
    archive_type: Optional[str] = None
    original_year: Optional[int] = None
    mention_count: int = 0
    confidence: float = 0.0


class SourceDetail(BaseModel):
    id: int
    name: str
    title: Optional[str] = None
    author: Optional[str] = None
    archive_type: Optional[str] = None
    original_year: Optional[int] = None
    content: Optional[str] = None
    entities_mentioned: int = 0


class MentionDetail(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    confidence: float
    extraction_model: Optional[str] = None


@router.get("/entity/{entity_type}/{entity_id}/sources")
async def get_entity_sources(
    entity_type: str,
    entity_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get source documents where an entity is mentioned."""
    if entity_type not in ['person', 'location', 'event', 'polity', 'period']:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    result = db.execute(text("""
        SELECT
            s.id, s.name, s.title, s.author, s.archive_type, s.original_year,
            COUNT(tm.id) as mention_count,
            AVG(tm.confidence) as avg_confidence
        FROM sources s
        JOIN text_mentions tm ON s.id = tm.source_id
        WHERE tm.entity_type = :entity_type AND tm.entity_id = :entity_id
        GROUP BY s.id, s.name, s.title, s.author, s.archive_type, s.original_year
        ORDER BY mention_count DESC
        LIMIT :limit
    """), {"entity_type": entity_type, "entity_id": entity_id, "limit": limit})

    items = [
        SourceSummary(
            id=row[0], name=row[1], title=row[2], author=row[3],
            archive_type=row[4], original_year=row[5],
            mention_count=row[6], confidence=float(row[7]) if row[7] else 0.0
        )
        for row in result
    ]

    return {"entity_type": entity_type, "entity_id": entity_id, "sources": items}


@router.get("/sources/{source_id}")
async def get_source_detail(
    source_id: int,
    include_content: bool = Query(True, description="Include full text content"),
    db: Session = Depends(get_db),
):
    """Get source document details including full text."""
    if include_content:
        result = db.execute(text("""
            SELECT id, name, title, author, archive_type, original_year, content
            FROM sources WHERE id = :source_id
        """), {"source_id": source_id})
    else:
        result = db.execute(text("""
            SELECT id, name, title, author, archive_type, original_year, NULL as content
            FROM sources WHERE id = :source_id
        """), {"source_id": source_id})

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")

    # Count entities mentioned in this source
    mention_count = db.execute(text("""
        SELECT COUNT(DISTINCT (entity_type, entity_id)) FROM text_mentions WHERE source_id = :source_id
    """), {"source_id": source_id}).scalar()

    return SourceDetail(
        id=row[0], name=row[1], title=row[2], author=row[3],
        archive_type=row[4], original_year=row[5], content=row[6],
        entities_mentioned=mention_count or 0
    )


@router.get("/sources/{source_id}/entities")
async def get_source_entities(
    source_id: int,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get all entities mentioned in a source document."""
    conditions = ["tm.source_id = :source_id"]
    params = {"source_id": source_id, "limit": limit}

    if entity_type:
        conditions.append("tm.entity_type = :entity_type")
        params["entity_type"] = entity_type

    where_clause = " AND ".join(conditions)

    result = db.execute(text(f"""
        SELECT
            tm.entity_type, tm.entity_id, tm.mention_text,
            tm.confidence, tm.extraction_model
        FROM text_mentions tm
        WHERE {where_clause}
        ORDER BY tm.confidence DESC, tm.entity_type
        LIMIT :limit
    """), params)

    items = [
        MentionDetail(
            entity_type=row[0], entity_id=row[1], entity_name=row[2],
            confidence=row[3], extraction_model=row[4]
        )
        for row in result
    ]

    # Group by entity type
    by_type = {}
    for item in items:
        if item.entity_type not in by_type:
            by_type[item.entity_type] = []
        by_type[item.entity_type].append(item)

    return {"source_id": source_id, "entities_by_type": by_type, "total": len(items)}


@router.get("/sources")
async def list_sources(
    q: Optional[str] = Query(None, description="Search by title/name"),
    archive_type: Optional[str] = Query(None, description="Filter by archive type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Browse source documents."""
    conditions = []
    params = {}

    if q:
        conditions.append("(title ILIKE :q OR name ILIKE :q)")
        params["q"] = f"%{q}%"
    if archive_type:
        conditions.append("archive_type = :archive_type")
        params["archive_type"] = archive_type

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Count total
    total = db.execute(text(f"SELECT COUNT(*) FROM sources WHERE {where_clause}"), params).scalar()

    # Fetch items
    params["limit"] = limit
    params["offset"] = offset
    result = db.execute(text(f"""
        SELECT id, name, title, author, archive_type, original_year
        FROM sources
        WHERE {where_clause}
        ORDER BY title NULLS LAST, name
        LIMIT :limit OFFSET :offset
    """), params)

    items = [
        {
            "id": row[0], "name": row[1], "title": row[2],
            "author": row[3], "archive_type": row[4], "original_year": row[5]
        }
        for row in result
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}
