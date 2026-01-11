"""
Historical Chain API - Event Connection Graph

다층 방향성 이벤트 그래프 CRUD 및 탐색 API
- 연결 조회/생성/수정/삭제
- 이벤트별 연결 조회
- 인물/장소 체인 조회
- 그래프 탐색
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime

from app.db.session import get_db

router = APIRouter(prefix="/chains", tags=["chains"])


# ============== Pydantic Models ==============

class EventSummary(BaseModel):
    id: int
    title: str
    date_start: Optional[int] = None
    date_end: Optional[int] = None

    class Config:
        from_attributes = True


class ConnectionBase(BaseModel):
    event_a_id: int
    event_b_id: int
    direction: Literal["forward", "backward", "bidirectional", "undirected"] = "forward"
    layer_type: Literal["person", "location", "causal", "thematic"] = "causal"
    layer_entity_id: Optional[int] = None
    connection_type: Optional[Literal["causes", "leads_to", "follows", "part_of", "concurrent", "related"]] = None
    manual_strength: Optional[float] = Field(None, ge=0, le=100)
    manual_reason: Optional[str] = None


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionUpdate(BaseModel):
    direction: Optional[Literal["forward", "backward", "bidirectional", "undirected"]] = None
    connection_type: Optional[Literal["causes", "leads_to", "follows", "part_of", "concurrent", "related"]] = None
    manual_strength: Optional[float] = Field(None, ge=0, le=100)
    manual_reason: Optional[str] = None
    curated_status: Optional[Literal["approved", "rejected", "pending"]] = None
    curation_note: Optional[str] = None


class ConnectionResponse(BaseModel):
    id: int
    event_a_id: int
    event_b_id: int
    event_a: Optional[EventSummary] = None
    event_b: Optional[EventSummary] = None
    direction: str
    layer_type: str
    layer_entity_id: Optional[int] = None
    connection_type: Optional[str] = None
    strength_score: float
    source_count: int
    time_distance: Optional[int] = None
    manual_strength: Optional[float] = None
    verification_status: str
    curated_status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConnectionListResponse(BaseModel):
    items: List[ConnectionResponse]
    total: int
    limit: int
    offset: int


class ChainNode(BaseModel):
    event: EventSummary
    depth: int
    connection_type: Optional[str] = None
    direction: str
    strength: float


class TraverseResponse(BaseModel):
    start_event: EventSummary
    nodes: List[ChainNode]
    total_nodes: int
    max_depth: int


class ChainStats(BaseModel):
    total_connections: int
    by_layer: dict
    by_type: dict
    by_verification: dict
    avg_strength: float


# ============== Helper Functions ==============

def get_event_summary(db: Session, event_id: int) -> Optional[EventSummary]:
    result = db.execute(text("""
        SELECT id, title, date_start, date_end FROM events WHERE id = :id
    """), {"id": event_id})
    row = result.fetchone()
    if row:
        return EventSummary(id=row[0], title=row[1], date_start=row[2], date_end=row[3])
    return None


def row_to_connection(row, event_a=None, event_b=None) -> ConnectionResponse:
    return ConnectionResponse(
        id=row[0],
        event_a_id=row[1],
        event_b_id=row[2],
        event_a=event_a,
        event_b=event_b,
        direction=row[3],
        layer_type=row[4],
        layer_entity_id=row[5],
        connection_type=row[6],
        strength_score=float(row[7]) if row[7] else 0,
        source_count=row[8] or 0,
        time_distance=row[9],
        manual_strength=float(row[10]) if row[10] else None,
        verification_status=row[11] or "unverified",
        curated_status=row[12],
        created_at=row[13]
    )


# ============== CRUD Endpoints ==============

@router.get("/", response_model=ConnectionListResponse)
async def list_connections(
    layer_type: Optional[str] = Query(None, description="Filter by layer: person, location, causal, thematic"),
    connection_type: Optional[str] = Query(None, description="Filter by type: causes, leads_to, follows, part_of, concurrent, related"),
    min_strength: Optional[float] = Query(None, description="Minimum strength score"),
    max_strength: Optional[float] = Query(None, description="Maximum strength score"),
    verification_status: Optional[str] = Query(None, description="Filter by verification: unverified, auto_verified, llm_verified, curated"),
    curated_status: Optional[str] = Query(None, description="Filter by curation: approved, rejected, pending"),
    sort_by: str = Query("strength_score", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List event connections with filters."""
    conditions = []
    params = {}

    if layer_type:
        conditions.append("ec.layer_type = :layer_type")
        params["layer_type"] = layer_type
    if connection_type:
        conditions.append("ec.connection_type = :connection_type")
        params["connection_type"] = connection_type
    if min_strength is not None:
        conditions.append("ec.strength_score >= :min_strength")
        params["min_strength"] = min_strength
    if max_strength is not None:
        conditions.append("ec.strength_score <= :max_strength")
        params["max_strength"] = max_strength
    if verification_status:
        conditions.append("ec.verification_status = :verification_status")
        params["verification_status"] = verification_status
    if curated_status:
        conditions.append("ec.curated_status = :curated_status")
        params["curated_status"] = curated_status

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Validate sort field
    allowed_sorts = ["strength_score", "source_count", "time_distance", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "strength_score"
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    # Count
    total = db.execute(
        text(f"SELECT COUNT(*) FROM event_connections ec WHERE {where_clause}"),
        params
    ).scalar()

    # Fetch
    params["limit"] = limit
    params["offset"] = offset
    result = db.execute(text(f"""
        SELECT
            ec.id, ec.event_a_id, ec.event_b_id, ec.direction, ec.layer_type,
            ec.layer_entity_id, ec.connection_type, ec.strength_score, ec.source_count,
            ec.time_distance, ec.manual_strength, ec.verification_status,
            ec.curated_status, ec.created_at,
            ea.title as event_a_title, ea.date_start as event_a_year,
            eb.title as event_b_title, eb.date_start as event_b_year
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        WHERE {where_clause}
        ORDER BY ec.{sort_by} {sort_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)

    items = []
    for row in result:
        conn = row_to_connection(row)
        conn.event_a = EventSummary(id=row[1], title=row[14], date_start=row[15])
        conn.event_b = EventSummary(id=row[2], title=row[16], date_start=row[17])
        items.append(conn)

    return ConnectionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/stats", response_model=ChainStats)
async def get_chain_stats(db: Session = Depends(get_db)):
    """Get statistics about event connections."""
    total = db.execute(text("SELECT COUNT(*) FROM event_connections")).scalar()

    # By layer
    layer_result = db.execute(text("""
        SELECT layer_type, COUNT(*) FROM event_connections GROUP BY layer_type
    """))
    by_layer = {row[0]: row[1] for row in layer_result}

    # By type
    type_result = db.execute(text("""
        SELECT COALESCE(connection_type, 'unclassified'), COUNT(*)
        FROM event_connections GROUP BY connection_type
    """))
    by_type = {row[0]: row[1] for row in type_result}

    # By verification
    verif_result = db.execute(text("""
        SELECT verification_status, COUNT(*) FROM event_connections GROUP BY verification_status
    """))
    by_verification = {row[0]: row[1] for row in verif_result}

    # Avg strength
    avg_strength = db.execute(text("SELECT AVG(strength_score) FROM event_connections")).scalar() or 0

    return ChainStats(
        total_connections=total,
        by_layer=by_layer,
        by_type=by_type,
        by_verification=by_verification,
        avg_strength=float(avg_strength)
    )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: int, db: Session = Depends(get_db)):
    """Get a single connection by ID."""
    result = db.execute(text("""
        SELECT
            ec.id, ec.event_a_id, ec.event_b_id, ec.direction, ec.layer_type,
            ec.layer_entity_id, ec.connection_type, ec.strength_score, ec.source_count,
            ec.time_distance, ec.manual_strength, ec.verification_status,
            ec.curated_status, ec.created_at
        FROM event_connections ec
        WHERE ec.id = :id
    """), {"id": connection_id})

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn = row_to_connection(row)
    conn.event_a = get_event_summary(db, conn.event_a_id)
    conn.event_b = get_event_summary(db, conn.event_b_id)
    return conn


@router.post("/", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    data: ConnectionCreate,
    db: Session = Depends(get_db),
):
    """Create a new event connection."""
    # Validate events exist
    event_a = get_event_summary(db, data.event_a_id)
    event_b = get_event_summary(db, data.event_b_id)
    if not event_a:
        raise HTTPException(status_code=404, detail=f"Event A (id={data.event_a_id}) not found")
    if not event_b:
        raise HTTPException(status_code=404, detail=f"Event B (id={data.event_b_id}) not found")

    # Calculate time distance
    time_distance = None
    if event_a.date_start and event_b.date_start:
        time_distance = abs(event_b.date_start - event_a.date_start)

    # Base strength (manual or calculated)
    base_strength = {"person": 10.0, "location": 5.0, "causal": 1.0, "thematic": 0.5}
    strength = data.manual_strength if data.manual_strength else base_strength.get(data.layer_type, 1.0)

    result = db.execute(text("""
        INSERT INTO event_connections
        (event_a_id, event_b_id, direction, layer_type, layer_entity_id,
         connection_type, strength_score, source_count, time_distance,
         manual_strength, manual_reason, verification_status, created_at, updated_at)
        VALUES
        (:event_a_id, :event_b_id, :direction, :layer_type, :layer_entity_id,
         :connection_type, :strength_score, 1, :time_distance,
         :manual_strength, :manual_reason, 'curated', NOW(), NOW())
        RETURNING id
    """), {
        "event_a_id": data.event_a_id,
        "event_b_id": data.event_b_id,
        "direction": data.direction,
        "layer_type": data.layer_type,
        "layer_entity_id": data.layer_entity_id,
        "connection_type": data.connection_type,
        "strength_score": strength,
        "time_distance": time_distance,
        "manual_strength": data.manual_strength,
        "manual_reason": data.manual_reason,
    })
    db.commit()

    new_id = result.fetchone()[0]
    return await get_connection(new_id, db)


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: int,
    data: ConnectionUpdate,
    db: Session = Depends(get_db),
):
    """Update an event connection."""
    # Check exists
    existing = db.execute(text("SELECT id FROM event_connections WHERE id = :id"), {"id": connection_id}).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Build update fields
    updates = []
    params = {"id": connection_id}

    if data.direction is not None:
        updates.append("direction = :direction")
        params["direction"] = data.direction
    if data.connection_type is not None:
        updates.append("connection_type = :connection_type")
        params["connection_type"] = data.connection_type
    if data.manual_strength is not None:
        updates.append("manual_strength = :manual_strength")
        params["manual_strength"] = data.manual_strength
    if data.manual_reason is not None:
        updates.append("manual_reason = :manual_reason")
        params["manual_reason"] = data.manual_reason
    if data.curated_status is not None:
        updates.append("curated_status = :curated_status")
        updates.append("curated_at = NOW()")
        params["curated_status"] = data.curated_status
    if data.curation_note is not None:
        updates.append("curation_note = :curation_note")
        params["curation_note"] = data.curation_note

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    update_clause = ", ".join(updates)

    db.execute(text(f"UPDATE event_connections SET {update_clause} WHERE id = :id"), params)
    db.commit()

    return await get_connection(connection_id, db)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    """Delete an event connection."""
    result = db.execute(text("DELETE FROM event_connections WHERE id = :id RETURNING id"), {"id": connection_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Connection not found")
    db.commit()
    return None


# ============== Event Connections ==============

@router.get("/event/{event_id}/connections", response_model=ConnectionListResponse)
async def get_event_connections(
    event_id: int,
    direction: Optional[str] = Query(None, description="Filter: outgoing, incoming, both"),
    layer_type: Optional[str] = Query(None),
    min_strength: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get all connections for a specific event."""
    conditions = []
    params = {"event_id": event_id}

    if direction == "outgoing":
        conditions.append("ec.event_a_id = :event_id")
    elif direction == "incoming":
        conditions.append("ec.event_b_id = :event_id")
    else:
        conditions.append("(ec.event_a_id = :event_id OR ec.event_b_id = :event_id)")

    if layer_type:
        conditions.append("ec.layer_type = :layer_type")
        params["layer_type"] = layer_type
    if min_strength:
        conditions.append("ec.strength_score >= :min_strength")
        params["min_strength"] = min_strength

    where_clause = " AND ".join(conditions)

    total = db.execute(
        text(f"SELECT COUNT(*) FROM event_connections ec WHERE {where_clause}"),
        params
    ).scalar()

    params["limit"] = limit
    params["offset"] = offset
    result = db.execute(text(f"""
        SELECT
            ec.id, ec.event_a_id, ec.event_b_id, ec.direction, ec.layer_type,
            ec.layer_entity_id, ec.connection_type, ec.strength_score, ec.source_count,
            ec.time_distance, ec.manual_strength, ec.verification_status,
            ec.curated_status, ec.created_at,
            ea.title, ea.date_start, eb.title, eb.date_start
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        WHERE {where_clause}
        ORDER BY ec.strength_score DESC
        LIMIT :limit OFFSET :offset
    """), params)

    items = []
    for row in result:
        conn = row_to_connection(row)
        conn.event_a = EventSummary(id=row[1], title=row[14], date_start=row[15])
        conn.event_b = EventSummary(id=row[2], title=row[16], date_start=row[17])
        items.append(conn)

    return ConnectionListResponse(items=items, total=total, limit=limit, offset=offset)


# ============== Entity Chains ==============

@router.get("/person/{person_id}")
async def get_person_chain(
    person_id: int,
    min_strength: float = Query(5.0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get event chain for a specific person."""
    # Get person info
    person = db.execute(text("SELECT id, name, birth_year, death_year FROM persons WHERE id = :id"),
                        {"id": person_id}).fetchone()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Get connections
    result = db.execute(text("""
        SELECT
            ec.id, ec.event_a_id, ec.event_b_id, ec.direction, ec.connection_type,
            ec.strength_score, ea.title, ea.date_start, eb.title, eb.date_start
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        WHERE ec.layer_type = 'person'
          AND ec.layer_entity_id = :person_id
          AND ec.strength_score >= :min_strength
        ORDER BY COALESCE(ea.date_start, 0), COALESCE(eb.date_start, 0)
        LIMIT :limit
    """), {"person_id": person_id, "min_strength": min_strength, "limit": limit})

    connections = []
    events_set = set()
    for row in result:
        connections.append({
            "id": row[0],
            "event_a": {"id": row[1], "title": row[6], "year": row[7]},
            "event_b": {"id": row[2], "title": row[8], "year": row[9]},
            "direction": row[3],
            "type": row[4],
            "strength": float(row[5])
        })
        events_set.add(row[1])
        events_set.add(row[2])

    return {
        "person": {"id": person[0], "name": person[1], "birth_year": person[2], "death_year": person[3]},
        "total_events": len(events_set),
        "total_connections": len(connections),
        "connections": connections
    }


@router.get("/location/{location_id}")
async def get_location_chain(
    location_id: int,
    min_strength: float = Query(3.0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get event chain for a specific location."""
    # Get location info
    location = db.execute(text("SELECT id, name, latitude, longitude FROM locations WHERE id = :id"),
                          {"id": location_id}).fetchone()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # Get connections
    result = db.execute(text("""
        SELECT
            ec.id, ec.event_a_id, ec.event_b_id, ec.direction, ec.connection_type,
            ec.strength_score, ea.title, ea.date_start, eb.title, eb.date_start
        FROM event_connections ec
        JOIN events ea ON ec.event_a_id = ea.id
        JOIN events eb ON ec.event_b_id = eb.id
        WHERE ec.layer_type = 'location'
          AND ec.layer_entity_id = :location_id
          AND ec.strength_score >= :min_strength
        ORDER BY COALESCE(ea.date_start, 0), COALESCE(eb.date_start, 0)
        LIMIT :limit
    """), {"location_id": location_id, "min_strength": min_strength, "limit": limit})

    connections = []
    events_set = set()
    for row in result:
        connections.append({
            "id": row[0],
            "event_a": {"id": row[1], "title": row[6], "year": row[7]},
            "event_b": {"id": row[2], "title": row[8], "year": row[9]},
            "direction": row[3],
            "type": row[4],
            "strength": float(row[5])
        })
        events_set.add(row[1])
        events_set.add(row[2])

    return {
        "location": {"id": location[0], "name": location[1], "lat": location[2], "lon": location[3]},
        "total_events": len(events_set),
        "total_connections": len(connections),
        "connections": connections
    }


# ============== Graph Traversal ==============

@router.get("/traverse", response_model=TraverseResponse)
async def traverse_chain(
    start_event_id: int = Query(..., description="Starting event ID"),
    max_depth: int = Query(3, ge=1, le=10, description="Maximum traversal depth"),
    min_strength: float = Query(5.0, description="Minimum connection strength"),
    direction: str = Query("forward", description="forward, backward, both"),
    layer_type: Optional[str] = Query(None, description="Filter by layer type"),
    limit: int = Query(50, ge=1, le=200, description="Max nodes to return"),
    db: Session = Depends(get_db),
):
    """Traverse the event chain from a starting event."""
    start_event = get_event_summary(db, start_event_id)
    if not start_event:
        raise HTTPException(status_code=404, detail="Start event not found")

    visited = set()
    nodes = []
    queue = [(start_event_id, 0, None, "start", 0)]  # (event_id, depth, conn_type, direction, strength)

    while queue and len(nodes) < limit:
        current_id, depth, conn_type, conn_dir, strength = queue.pop(0)

        if current_id in visited or depth > max_depth:
            continue
        visited.add(current_id)

        if current_id != start_event_id:
            event = get_event_summary(db, current_id)
            if event:
                nodes.append(ChainNode(
                    event=event,
                    depth=depth,
                    connection_type=conn_type,
                    direction=conn_dir,
                    strength=strength
                ))

        if depth >= max_depth:
            continue

        # Build query for next connections
        conditions = ["ec.strength_score >= :min_strength"]
        params = {"event_id": current_id, "min_strength": min_strength}

        if direction == "forward":
            conditions.append("ec.event_a_id = :event_id")
        elif direction == "backward":
            conditions.append("ec.event_b_id = :event_id")
        else:
            conditions.append("(ec.event_a_id = :event_id OR ec.event_b_id = :event_id)")

        if layer_type:
            conditions.append("ec.layer_type = :layer_type")
            params["layer_type"] = layer_type

        where_clause = " AND ".join(conditions)

        result = db.execute(text(f"""
            SELECT ec.event_a_id, ec.event_b_id, ec.connection_type, ec.direction, ec.strength_score
            FROM event_connections ec
            WHERE {where_clause}
            ORDER BY ec.strength_score DESC
            LIMIT 20
        """), params)

        for row in result:
            next_id = row[1] if row[0] == current_id else row[0]
            if next_id not in visited:
                conn_direction = "outgoing" if row[0] == current_id else "incoming"
                queue.append((next_id, depth + 1, row[2], conn_direction, float(row[4])))

    return TraverseResponse(
        start_event=start_event,
        nodes=nodes,
        total_nodes=len(nodes),
        max_depth=max_depth
    )
