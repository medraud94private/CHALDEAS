"""
Search API endpoints.

검색 이원화:
- /search/basic: BM25 키워드 검색 (무료, 비공개)
- /search/advanced: BM25 + AI (마스터 번호 부여, 검색 기록 공개)
"""
from fastapi import APIRouter, Query, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.services.json_data import get_data_service
from app.services.hybrid_search import get_hybrid_search_service
from app.services.master_service import get_master_service

router = APIRouter()


class AdvancedSearchRequest(BaseModel):
    """고급검색 요청"""
    query: str = Field(..., min_length=1, description="Search query")
    openai_api_key: str = Field(..., description="User's OpenAI API key")
    limit: int = Field(10, ge=1, le=50)
    use_ai: bool = Field(True, description="Generate AI response")


class MasterInfo(BaseModel):
    """마스터 정보"""
    master_number: int
    nickname: Optional[str]
    basic_search_count: int
    advanced_search_count: int


class AdvancedSearchResponse(BaseModel):
    """고급검색 응답"""
    query: str
    search_type: str
    master: MasterInfo
    results: List[Dict[str, Any]]
    ai_response: Optional[Dict[str, Any]]
    is_public: bool
    total: int


# ============================================================
# 일반검색 (Basic Search) - BM25 키워드 매칭
# ============================================================

@router.get("/basic")
async def basic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    type_filter: Optional[str] = Query(None, description="Filter by type: event, person, location, all"),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token")
):
    """
    일반검색 - BM25 키워드 매칭

    특징:
    - 무료
    - AI 없음
    - 검색 기록 비공개
    - 마스터 번호 불필요

    Example: /search/basic?q=마라톤 전투
    """
    hybrid_service = get_hybrid_search_service()
    results = hybrid_service.basic_search(q, limit=limit, type_filter=type_filter)

    # 선택적: 세션 토큰이 있으면 검색 카운트 증가
    if x_session_token:
        master_service = get_master_service()
        master = master_service.get_or_create_master(x_session_token)
        master_service.increment_search_count(x_session_token, "basic")

    return results


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    통합 검색 (레거시 호환)

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


# ============================================================
# 고급검색 (Advanced Search) - BM25 + Vector + AI
# ============================================================

@router.post("/advanced", response_model=AdvancedSearchResponse)
async def advanced_search(
    request: AdvancedSearchRequest,
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token")
):
    """
    고급검색 - BM25 + Vector + AI

    특징:
    - 유저가 자신의 OpenAI API 키 제공
    - 마스터 번호 자동 부여 (첫 고급검색 시)
    - 검색 기록 공개 (칼데아 아카이브)
    - AI 응답 생성

    Request body:
    {
        "query": "마라톤 전투와 살라미스 해전 비교",
        "openai_api_key": "sk-...",
        "limit": 10,
        "use_ai": true
    }

    Headers:
    - X-Session-Token: (선택) 세션 유지용

    Response:
    - master: 마스터 정보 (번호 포함)
    - results: 검색 결과
    - ai_response: AI 생성 응답
    - is_public: 공개 여부 (항상 true)
    """
    # 1. 마스터 조회/생성
    master_service = get_master_service()
    master = master_service.get_or_create_master(x_session_token)

    # 2. 고급검색 수행
    try:
        # RAG 서비스 생성 (유저 API 키 사용)
        from app.services.rag_service import RAGService
        rag_service = RAGService(api_key=request.openai_api_key)

        hybrid_service = get_hybrid_search_service(rag_service=rag_service)

        results = await hybrid_service.advanced_search(
            query=request.query,
            limit=request.limit,
            use_ai=request.use_ai
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Search failed: {str(e)}. Check your OpenAI API key."
        )

    # 3. 검색 카운트 및 로그 기록
    master_service.increment_search_count(master["session_token"], "advanced")

    log_entry = master_service.log_search(
        master_number=master["master_number"],
        query=request.query,
        search_type="advanced",
        response_summary=results.get("ai_response", {}).get("answer", "")[:200] if results.get("ai_response") else None,
        intent=results.get("ai_response", {}).get("intent") if results.get("ai_response") else None,
        is_public=True  # 고급검색은 항상 공개
    )

    return AdvancedSearchResponse(
        query=request.query,
        search_type="advanced",
        master=MasterInfo(
            master_number=master["master_number"],
            nickname=master.get("nickname"),
            basic_search_count=master["basic_search_count"],
            advanced_search_count=master["advanced_search_count"]
        ),
        results=results.get("results", []),
        ai_response=results.get("ai_response"),
        is_public=True,
        total=results.get("total", 0)
    )


# ============================================================
# 마스터 및 공개 로그 조회
# ============================================================

@router.get("/logs/public")
async def get_public_search_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    공개된 고급검색 기록 조회 (칼데아 아카이브)

    최근 검색 기록을 공개하여 다른 마스터들이 어떤 질문을 했는지 볼 수 있음
    """
    master_service = get_master_service()
    logs = master_service.get_public_search_logs(limit=limit, offset=offset)

    return {
        "logs": logs,
        "count": len(logs),
        "offset": offset
    }


@router.get("/master/{master_number}")
async def get_master_info(master_number: int):
    """마스터 정보 조회"""
    master_service = get_master_service()
    master = master_service.get_master_by_number(master_number)

    if not master:
        raise HTTPException(status_code=404, detail="Master not found")

    # 공개 정보만 반환
    return {
        "master_number": master["master_number"],
        "nickname": master.get("nickname"),
        "advanced_search_count": master["advanced_search_count"],
        "created_at": master["created_at"]
    }


@router.get("/master/{master_number}/history")
async def get_master_search_history(
    master_number: int,
    limit: int = Query(20, ge=1, le=100)
):
    """마스터의 공개 검색 기록 조회"""
    master_service = get_master_service()
    history = master_service.get_master_search_history(master_number, include_private=False)

    return {
        "master_number": master_number,
        "history": history[:limit],
        "count": len(history)
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
