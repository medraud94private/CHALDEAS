"""
Source service - Business logic for sources and text mentions.

Provides:
- Source listing with filters
- Source details
- Person-source relationships via text_mentions
- Source-person relationships
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.models.source import Source


def get_sources(
    db: Session,
    source_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """
    Get sources with optional filtering.
    Returns sources with mention counts.
    """
    # Base query
    query = db.execute(text("""
        SELECT
            s.id,
            s.name,
            s.title,
            s.type,
            s.author,
            COUNT(DISTINCT tm.id) as mention_count,
            COUNT(DISTINCT CASE WHEN tm.entity_type = 'person' THEN tm.entity_id END) as person_count
        FROM sources s
        LEFT JOIN text_mentions tm ON tm.source_id = s.id
        WHERE (:source_type IS NULL OR s.type = :source_type)
        GROUP BY s.id
        HAVING COUNT(DISTINCT tm.id) > 0
        ORDER BY mention_count DESC
        LIMIT :limit OFFSET :offset
    """), {
        "source_type": source_type,
        "limit": limit,
        "offset": offset
    })

    items = [dict(row._mapping) for row in query.fetchall()]

    # Get total count
    count_result = db.execute(text("""
        SELECT COUNT(DISTINCT s.id)
        FROM sources s
        JOIN text_mentions tm ON tm.source_id = s.id
        WHERE (:source_type IS NULL OR s.type = :source_type)
    """), {"source_type": source_type})

    total = count_result.scalar() or 0

    return items, total


def get_source_by_id(db: Session, source_id: int) -> Optional[dict]:
    """Get source details by ID."""
    result = db.execute(text("""
        SELECT
            s.id,
            s.name,
            s.title,
            s.type,
            s.url,
            s.author,
            s.archive_type,
            COALESCE(s.reliability, 3) as reliability,
            s.description,
            s.publication_year,
            s.original_year,
            s.language,
            s.document_id,
            COUNT(DISTINCT tm.id) as mention_count,
            COUNT(DISTINCT CASE WHEN tm.entity_type = 'person' THEN tm.entity_id END) as person_count,
            COUNT(DISTINCT CASE WHEN tm.entity_type = 'location' THEN tm.entity_id END) as location_count,
            COUNT(DISTINCT CASE WHEN tm.entity_type = 'event' THEN tm.entity_id END) as event_count
        FROM sources s
        LEFT JOIN text_mentions tm ON tm.source_id = s.id
        WHERE s.id = :source_id
        GROUP BY s.id
    """), {"source_id": source_id})

    row = result.fetchone()
    if row:
        return dict(row._mapping)
    return None


def get_source_persons(
    db: Session,
    source_id: int,
    limit: int = 100,
    offset: int = 0,
    min_mentions: int = 1,
) -> Tuple[List[dict], int]:
    """Get persons mentioned in a source."""
    query = db.execute(text("""
        SELECT
            p.id,
            p.name,
            p.name_ko,
            p.birth_year,
            p.death_year,
            p.wikidata_id,
            COUNT(tm.id) as mention_count
        FROM persons p
        JOIN text_mentions tm ON tm.entity_id = p.id AND tm.entity_type = 'person'
        WHERE tm.source_id = :source_id
        GROUP BY p.id
        HAVING COUNT(tm.id) >= :min_mentions
        ORDER BY mention_count DESC
        LIMIT :limit OFFSET :offset
    """), {
        "source_id": source_id,
        "min_mentions": min_mentions,
        "limit": limit,
        "offset": offset
    })

    items = [dict(row._mapping) for row in query.fetchall()]

    # Get total count
    count_result = db.execute(text("""
        SELECT COUNT(DISTINCT p.id)
        FROM persons p
        JOIN text_mentions tm ON tm.entity_id = p.id AND tm.entity_type = 'person'
        WHERE tm.source_id = :source_id
        GROUP BY p.id
        HAVING COUNT(tm.id) >= :min_mentions
    """), {"source_id": source_id, "min_mentions": min_mentions})

    total = count_result.scalar() or 0

    return items, total


def get_person_sources(
    db: Session,
    person_id: int,
    limit: int = 20,
    include_contexts: bool = True,
    max_contexts: int = 3,
) -> Tuple[List[dict], int]:
    """
    Get sources that mention a person.
    Includes mention contexts if requested.
    """
    # Get sources with mention counts
    query = db.execute(text("""
        SELECT
            s.id,
            s.name,
            s.title,
            s.type,
            s.author,
            COUNT(tm.id) as mention_count
        FROM sources s
        JOIN text_mentions tm ON tm.source_id = s.id
        WHERE tm.entity_type = 'person' AND tm.entity_id = :person_id
        GROUP BY s.id
        ORDER BY mention_count DESC
        LIMIT :limit
    """), {"person_id": person_id, "limit": limit})

    sources = []
    for row in query.fetchall():
        source_data = dict(row._mapping)
        source_data["person_count"] = 0  # Not needed for this view

        # Get contexts if requested
        if include_contexts:
            context_query = db.execute(text("""
                SELECT mention_text, context_text, confidence, chunk_index
                FROM text_mentions
                WHERE source_id = :source_id
                  AND entity_type = 'person'
                  AND entity_id = :person_id
                ORDER BY confidence DESC
                LIMIT :max_contexts
            """), {
                "source_id": source_data["id"],
                "person_id": person_id,
                "max_contexts": max_contexts
            })

            source_data["mentions"] = [
                {
                    "mention_text": ctx.mention_text or "",
                    "context_text": ctx.context_text,
                    "confidence": ctx.confidence,
                    "chunk_index": ctx.chunk_index
                }
                for ctx in context_query.fetchall()
            ]
        else:
            source_data["mentions"] = []

        sources.append(source_data)

    # Get total count
    count_result = db.execute(text("""
        SELECT COUNT(DISTINCT s.id)
        FROM sources s
        JOIN text_mentions tm ON tm.source_id = s.id
        WHERE tm.entity_type = 'person' AND tm.entity_id = :person_id
    """), {"person_id": person_id})

    total = count_result.scalar() or 0

    return sources, total


def get_source_mentions(
    db: Session,
    source_id: int,
    entity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """Get all mentions in a source with context."""
    query = db.execute(text("""
        SELECT
            tm.id,
            tm.entity_type,
            tm.entity_id,
            tm.mention_text,
            tm.context_text,
            tm.confidence,
            tm.chunk_index,
            CASE
                WHEN tm.entity_type = 'person' THEN p.name
                WHEN tm.entity_type = 'location' THEN l.name
                WHEN tm.entity_type = 'event' THEN e.title
                ELSE NULL
            END as entity_name
        FROM text_mentions tm
        LEFT JOIN persons p ON tm.entity_type = 'person' AND tm.entity_id = p.id
        LEFT JOIN locations l ON tm.entity_type = 'location' AND tm.entity_id = l.id
        LEFT JOIN events e ON tm.entity_type = 'event' AND tm.entity_id = e.id
        WHERE tm.source_id = :source_id
          AND (:entity_type IS NULL OR tm.entity_type = :entity_type)
        ORDER BY tm.chunk_index, tm.id
        LIMIT :limit OFFSET :offset
    """), {
        "source_id": source_id,
        "entity_type": entity_type,
        "limit": limit,
        "offset": offset
    })

    items = [dict(row._mapping) for row in query.fetchall()]

    # Get total
    count_result = db.execute(text("""
        SELECT COUNT(*)
        FROM text_mentions
        WHERE source_id = :source_id
          AND (:entity_type IS NULL OR entity_type = :entity_type)
    """), {"source_id": source_id, "entity_type": entity_type})

    total = count_result.scalar() or 0

    return items, total


def search_sources(
    db: Session,
    query: str,
    limit: int = 20,
) -> List[dict]:
    """Search sources by title or name."""
    search_pattern = f"%{query}%"

    result = db.execute(text("""
        SELECT
            s.id,
            s.name,
            s.title,
            s.type,
            s.author,
            COUNT(DISTINCT tm.id) as mention_count
        FROM sources s
        LEFT JOIN text_mentions tm ON tm.source_id = s.id
        WHERE s.name ILIKE :pattern
           OR s.title ILIKE :pattern
           OR s.author ILIKE :pattern
        GROUP BY s.id
        ORDER BY mention_count DESC
        LIMIT :limit
    """), {"pattern": search_pattern, "limit": limit})

    return [dict(row._mapping) for row in result.fetchall()]
