"""
Story API - Person/Place/Arc Story for immersive historical exploration.

인물/장소/아크의 스토리를 지도 위 노드로 시각화하기 위한 API.
기존 chains.py와 별개로, Story UI에 최적화된 응답 형식 제공.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel

from app.db.session import get_db

router = APIRouter()


# ============== Pydantic Models ==============

class StoryLocation(BaseModel):
    """위치 정보 (지도 표시용)"""
    name: str
    name_ko: Optional[str] = None
    lat: float
    lng: float


class StoryNode(BaseModel):
    """스토리 노드 (지도 위 한 지점)"""
    order: int
    event_id: int
    title: str
    title_ko: Optional[str] = None
    year: Optional[int] = None
    year_end: Optional[int] = None
    location: Optional[StoryLocation] = None
    node_type: str = "normal"  # birth, major, battle, political, death, normal
    description: Optional[str] = None


class StoryPerson(BaseModel):
    """인물 정보"""
    id: int
    name: str
    name_ko: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    role: Optional[str] = None


class MapView(BaseModel):
    """지도 뷰 설정"""
    center_lat: float
    center_lng: float
    zoom: int = 6


class PersonStoryResponse(BaseModel):
    """Person Story 응답"""
    person: StoryPerson
    nodes: List[StoryNode]
    total_nodes: int
    map_view: MapView


# ============== Helper Functions ==============

def determine_node_type(event_title: str, year: int, birth_year: int, death_year: int) -> str:
    """이벤트 제목과 연도로 노드 타입 결정"""
    title_lower = event_title.lower() if event_title else ""

    # Birth/Death check by year
    if birth_year and year == birth_year:
        return "birth"
    if death_year and year == death_year:
        return "death"

    # Keyword-based detection
    if any(word in title_lower for word in ["birth", "born", "출생", "탄생"]):
        return "birth"
    if any(word in title_lower for word in ["death", "died", "execution", "화형", "사망", "처형", "순교"]):
        return "death"
    if any(word in title_lower for word in ["battle", "siege", "war", "전투", "포위", "공방"]):
        return "battle"
    if any(word in title_lower for word in ["coronation", "treaty", "대관", "조약", "즉위"]):
        return "political"
    if any(word in title_lower for word in ["victory", "liberation", "해방", "승리"]):
        return "major"

    return "normal"


def calculate_map_view(nodes: List[dict]) -> MapView:
    """노드들의 좌표로 적절한 지도 뷰 계산"""
    if not nodes:
        return MapView(center_lat=48.0, center_lng=2.0, zoom=5)

    lats = [n["lat"] for n in nodes if n.get("lat")]
    lngs = [n["lng"] for n in nodes if n.get("lng")]

    if not lats or not lngs:
        return MapView(center_lat=48.0, center_lng=2.0, zoom=5)

    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)

    # Calculate zoom based on spread
    lat_spread = max(lats) - min(lats)
    lng_spread = max(lngs) - min(lngs)
    spread = max(lat_spread, lng_spread)

    if spread < 2:
        zoom = 8
    elif spread < 5:
        zoom = 7
    elif spread < 10:
        zoom = 6
    elif spread < 20:
        zoom = 5
    else:
        zoom = 4

    return MapView(center_lat=center_lat, center_lng=center_lng, zoom=zoom)


# ============== API Endpoints ==============

@router.get("/person/{person_id}", response_model=PersonStoryResponse)
async def get_person_story(
    person_id: int,
    min_strength: float = Query(0, description="Minimum connection strength"),
    db: Session = Depends(get_db),
):
    """
    Get Person Story - 인물의 생애를 지도 노드로 반환.

    event_connections 테이블에서 해당 인물과 연결된 이벤트들을
    시간순으로 정렬하여 반환. 각 이벤트의 위치 좌표 포함.
    """
    # 1. Get person info
    person_result = db.execute(text("""
        SELECT id, name, name_ko, birth_year, death_year, role
        FROM persons
        WHERE id = :person_id
    """), {"person_id": person_id})

    person_row = person_result.fetchone()
    if not person_row:
        raise HTTPException(status_code=404, detail="Person not found")

    person = StoryPerson(
        id=person_row[0],
        name=person_row[1],
        name_ko=person_row[2],
        birth_year=person_row[3],
        death_year=person_row[4],
        role=person_row[5]
    )

    # 2. Get events from event_connections (person layer)
    events_result = db.execute(text("""
        WITH person_events AS (
            -- event_a에서 가져온 이벤트
            SELECT DISTINCT
                e.id as event_id,
                e.title,
                e.title_ko,
                e.description,
                e.date_start as year,
                e.date_end as year_end,
                l.name as loc_name,
                l.name_ko as loc_name_ko,
                l.latitude as lat,
                l.longitude as lng,
                ec.strength_score
            FROM event_connections ec
            JOIN events e ON ec.event_a_id = e.id
            LEFT JOIN locations l ON e.primary_location_id = l.id
            WHERE ec.layer_type = 'person'
              AND ec.layer_entity_id = :person_id
              AND ec.strength_score >= :min_strength

            UNION

            -- event_b에서 가져온 이벤트
            SELECT DISTINCT
                e.id as event_id,
                e.title,
                e.title_ko,
                e.description,
                e.date_start as year,
                e.date_end as year_end,
                l.name as loc_name,
                l.name_ko as loc_name_ko,
                l.latitude as lat,
                l.longitude as lng,
                ec.strength_score
            FROM event_connections ec
            JOIN events e ON ec.event_b_id = e.id
            LEFT JOIN locations l ON e.primary_location_id = l.id
            WHERE ec.layer_type = 'person'
              AND ec.layer_entity_id = :person_id
              AND ec.strength_score >= :min_strength
        )
        SELECT DISTINCT event_id, title, title_ko, description, year, year_end,
                        loc_name, loc_name_ko, lat, lng
        FROM person_events
        WHERE year IS NOT NULL
        ORDER BY year
    """), {"person_id": person_id, "min_strength": min_strength})

    # 3. Build nodes
    nodes = []
    node_locs = []

    for idx, row in enumerate(events_result):
        event_id, title, title_ko, description, year, year_end, loc_name, loc_name_ko, lat, lng = row

        # Location (if available)
        location = None
        if lat and lng:
            location = StoryLocation(
                name=loc_name or "Unknown",
                name_ko=loc_name_ko,
                lat=float(lat),
                lng=float(lng)
            )
            node_locs.append({"lat": float(lat), "lng": float(lng)})

        # Determine node type
        node_type = determine_node_type(
            title,
            year,
            person.birth_year,
            person.death_year
        )

        nodes.append(StoryNode(
            order=idx,
            event_id=event_id,
            title=title,
            title_ko=title_ko,
            year=year,
            year_end=year_end,
            location=location,
            node_type=node_type,
            description=description[:200] if description else None
        ))

    # 4. Calculate map view
    map_view = calculate_map_view(node_locs)

    return PersonStoryResponse(
        person=person,
        nodes=nodes,
        total_nodes=len(nodes),
        map_view=map_view
    )


@router.get("/person/{person_id}/check")
async def check_person_story_available(
    person_id: int,
    db: Session = Depends(get_db),
):
    """
    Check if Person Story is available.

    인물에 대한 스토리 데이터가 있는지 빠르게 확인.
    """
    # Check person exists
    person = db.execute(text("""
        SELECT id, name FROM persons WHERE id = :person_id
    """), {"person_id": person_id}).fetchone()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Count events in event_connections
    count = db.execute(text("""
        SELECT COUNT(DISTINCT CASE
            WHEN event_a_id IS NOT NULL THEN event_a_id
            ELSE event_b_id
        END)
        FROM event_connections
        WHERE layer_type = 'person' AND layer_entity_id = :person_id
    """), {"person_id": person_id}).scalar()

    return {
        "person_id": person_id,
        "person_name": person[1],
        "has_story": count > 0,
        "event_count": count
    }
