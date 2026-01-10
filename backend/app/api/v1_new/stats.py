"""
Statistics API - Database overview and analytics.

Provides:
- Overall database statistics
- Timeline distribution (events per era)
- Geographic distribution (events per country/region)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db

router = APIRouter(prefix="/stats", tags=["statistics"])


# ============== Response Models ==============

class OverviewStats(BaseModel):
    events: dict
    locations: dict
    persons: dict
    sources: dict
    last_updated: str


class TimelineBucket(BaseModel):
    year_start: int
    year_end: int
    count: int
    label: str


class GeographyStats(BaseModel):
    country: str
    count: int
    percentage: float


# ============== Endpoints ==============

@router.get("/overview", response_model=OverviewStats)
async def get_overview_stats(db: Session = Depends(get_db)):
    """
    Get overall database statistics.

    Returns counts and coverage for all major entity types.
    """
    # Events stats
    events_total = db.execute(text("SELECT COUNT(*) FROM events")).scalar()
    events_with_location = db.execute(text(
        "SELECT COUNT(*) FROM events WHERE primary_location_id IS NOT NULL"
    )).scalar()
    events_with_year = db.execute(text(
        "SELECT COUNT(*) FROM events WHERE date_start IS NOT NULL"
    )).scalar()
    events_enriched = db.execute(text(
        "SELECT COUNT(*) FROM events WHERE enriched_by IS NOT NULL"
    )).scalar()

    # Locations stats
    locations_total = db.execute(text("SELECT COUNT(*) FROM locations")).scalar()
    locations_with_coords = db.execute(text(
        "SELECT COUNT(*) FROM locations WHERE latitude IS NOT NULL"
    )).scalar()
    locations_with_country = db.execute(text(
        "SELECT COUNT(*) FROM locations WHERE country IS NOT NULL"
    )).scalar()

    # Persons stats
    persons_total = db.execute(text("SELECT COUNT(*) FROM persons")).scalar()
    persons_with_birth = db.execute(text(
        "SELECT COUNT(*) FROM persons WHERE birth_year IS NOT NULL"
    )).scalar()
    persons_enriched = db.execute(text(
        "SELECT COUNT(*) FROM persons WHERE enriched_by IS NOT NULL"
    )).scalar()
    persons_major = db.execute(text(
        "SELECT COUNT(*) FROM persons WHERE mention_count >= 3"
    )).scalar()

    # Sources stats
    sources_total = db.execute(text("SELECT COUNT(*) FROM sources")).scalar()
    text_mentions = db.execute(text("SELECT COUNT(*) FROM text_mentions")).scalar()

    return OverviewStats(
        events={
            "total": events_total,
            "with_location": events_with_location,
            "with_year": events_with_year,
            "enriched": events_enriched,
            "location_coverage": round(events_with_location / events_total * 100, 1) if events_total else 0,
        },
        locations={
            "total": locations_total,
            "with_coordinates": locations_with_coords,
            "with_country": locations_with_country,
            "country_coverage": round(locations_with_country / locations_total * 100, 1) if locations_total else 0,
        },
        persons={
            "total": persons_total,
            "with_birth_year": persons_with_birth,
            "enriched": persons_enriched,
            "major_figures": persons_major,
            "birth_coverage": round(persons_with_birth / persons_total * 100, 1) if persons_total else 0,
        },
        sources={
            "total": sources_total,
            "text_mentions": text_mentions,
        },
        last_updated=datetime.now().isoformat()
    )


@router.get("/timeline")
async def get_timeline_stats(
    bucket_size: int = Query(100, description="Years per bucket"),
    min_year: int = Query(-3000, description="Start year (BCE as negative)"),
    max_year: int = Query(2025, description="End year"),
    db: Session = Depends(get_db),
):
    """
    Get event distribution over time.

    Returns event counts grouped by time periods.
    """
    result = db.execute(text("""
        SELECT
            FLOOR(date_start / :bucket_size) * :bucket_size as year_bucket,
            COUNT(*) as count
        FROM events
        WHERE date_start IS NOT NULL
          AND date_start >= :min_year
          AND date_start <= :max_year
        GROUP BY year_bucket
        ORDER BY year_bucket
    """), {
        "bucket_size": bucket_size,
        "min_year": min_year,
        "max_year": max_year
    })

    buckets = []
    for row in result:
        year_start = int(row[0])
        year_end = year_start + bucket_size - 1

        # Create readable label
        if year_start < 0:
            label = f"{abs(year_start)}-{abs(year_end)} BCE"
        else:
            label = f"{year_start}-{year_end} CE"

        buckets.append({
            "year_start": year_start,
            "year_end": year_end,
            "count": row[1],
            "label": label
        })

    return {
        "bucket_size": bucket_size,
        "range": {"min": min_year, "max": max_year},
        "buckets": buckets,
        "total_events": sum(b["count"] for b in buckets)
    }


@router.get("/geography")
async def get_geography_stats(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get event distribution by geography.

    Returns event counts grouped by country.
    """
    # Events by country (via locations)
    result = db.execute(text("""
        SELECT
            COALESCE(l.country, 'Unknown') as country,
            COUNT(*) as count
        FROM events e
        JOIN locations l ON e.primary_location_id = l.id
        WHERE l.country IS NOT NULL
        GROUP BY l.country
        ORDER BY count DESC
        LIMIT :limit
    """), {"limit": limit})

    countries = []
    total = 0
    for row in result:
        countries.append({
            "country": row[0],
            "count": row[1]
        })
        total += row[1]

    # Add percentage
    for c in countries:
        c["percentage"] = round(c["count"] / total * 100, 1) if total else 0

    return {
        "countries": countries,
        "total_events": total,
        "country_count": len(countries)
    }


@router.get("/categories")
async def get_category_stats(db: Session = Depends(get_db)):
    """
    Get event distribution by category.
    """
    result = db.execute(text("""
        SELECT
            COALESCE(c.name, 'Uncategorized') as category,
            COUNT(*) as count
        FROM events e
        LEFT JOIN categories c ON e.category_id = c.id
        GROUP BY c.name
        ORDER BY count DESC
    """))

    categories = [{"category": row[0], "count": row[1]} for row in result]
    total = sum(c["count"] for c in categories)

    for c in categories:
        c["percentage"] = round(c["count"] / total * 100, 1) if total else 0

    return {
        "categories": categories,
        "total_events": total
    }


@router.get("/enrichment")
async def get_enrichment_stats(db: Session = Depends(get_db)):
    """
    Get enrichment pipeline statistics.
    """
    # Events enrichment
    events_by_model = db.execute(text("""
        SELECT enriched_by, COUNT(*)
        FROM events
        WHERE enriched_by IS NOT NULL
        GROUP BY enriched_by
    """)).fetchall()

    # Persons enrichment
    persons_by_model = db.execute(text("""
        SELECT enriched_by, COUNT(*)
        FROM persons
        WHERE enriched_by IS NOT NULL
        GROUP BY enriched_by
    """)).fetchall()

    # Locations enrichment
    locations_by_source = db.execute(text("""
        SELECT geocoded_by, COUNT(*)
        FROM locations
        WHERE geocoded_by IS NOT NULL
        GROUP BY geocoded_by
    """)).fetchall()

    return {
        "events": {
            "by_model": {row[0]: row[1] for row in events_by_model},
            "total_enriched": sum(row[1] for row in events_by_model)
        },
        "persons": {
            "by_model": {row[0]: row[1] for row in persons_by_model},
            "total_enriched": sum(row[1] for row in persons_by_model)
        },
        "locations": {
            "by_source": {row[0]: row[1] for row in locations_by_source},
            "total_enriched": sum(row[1] for row in locations_by_source)
        }
    }
