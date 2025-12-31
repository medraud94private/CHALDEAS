"""
SHEBA Chat API endpoints.

Provides conversational interface to the historical knowledge system.
This is where SHEBA (observation) + LOGOS (proposal) + LAPLACE (explanation)
come together.
"""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.trismegistus.orchestrator import Orchestrator

router = APIRouter()

# History Agent (lazy initialization)
_history_agent = None

# RAG Service (lazy initialization)
_rag_service = None

def get_rag_service():
    """Get or create RAG service instance."""
    global _rag_service
    if _rag_service is None:
        try:
            from app.services.rag_service import RAGService
            from app.config import get_settings
            settings = get_settings()
            _rag_service = RAGService(api_key=settings.openai_api_key)
        except Exception as e:
            print(f"Warning: RAG service not available: {e}")
            import traceback
            traceback.print_exc()
            return None
    return _rag_service


def get_history_agent():
    """Get or create History Agent instance with RAG service."""
    global _history_agent
    if _history_agent is None:
        try:
            from app.core.sheba.history_agent import HistoryAgent
            from app.config import get_settings
            settings = get_settings()
            rag_service = get_rag_service()
            _history_agent = HistoryAgent(
                rag_service=rag_service,
                api_key=settings.openai_api_key
            )
        except Exception as e:
            print(f"Warning: History Agent not available: {e}")
            return None
    return _history_agent


class RAGFilters(BaseModel):
    """Filters for RAG search."""
    category: Optional[str] = None  # battle, treaty, discovery, etc.
    date_from: Optional[int] = None  # e.g., -500 for 500 BCE
    date_to: Optional[int] = None    # e.g., 1500 for 1500 CE


class RAGRequest(BaseModel):
    """Request for RAG-based chat."""
    query: str
    context_limit: int = 5
    filters: Optional[RAGFilters] = None


class RAGResponseModel(BaseModel):
    """Response from RAG pipeline."""
    answer: str
    sources: List[dict]
    confidence: float
    related_events: List[dict]
    query_interpretation: str


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Process a natural language query about history.

    Flow:
    1. SHEBA observes the query and identifies relevant context
    2. LOGOS proposes a response
    3. PAPERMOON verifies factual accuracy
    4. LAPLACE attaches sources and explanations

    Example queries:
    - "What happened in 490 BCE at Marathon?"
    - "Tell me about Socrates and his students"
    - "What scientific discoveries were made during the Renaissance?"
    """
    try:
        orchestrator = Orchestrator(db)
        response = await orchestrator.process_query(request.query, request.context)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/observe")
async def observe(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    SHEBA observation endpoint.

    Returns structured observation without LLM processing.
    Useful for exploring what data is available for a given context.
    """
    try:
        orchestrator = Orchestrator(db)
        observation = await orchestrator.observe_only(request.query)
        return observation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag", response_model=RAGResponseModel)
async def rag_chat(request: RAGRequest):
    """
    RAG-based chat endpoint using vector search.

    Uses:
    - text-embedding-3-large for semantic search
    - gpt-5-nano for response generation
    - pgvector for vector storage

    Example:
        POST /api/v1/chat/rag
        {"query": "마라톤 전투에 대해 알려줘", "context_limit": 5}

        With filters:
        {"query": "고대 전투", "filters": {"category": "battle", "date_from": -500, "date_to": 500}}
    """
    rag_service = get_rag_service()

    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG service not available. Check if pgvector is running and events are indexed."
        )

    # Convert filters to dict if provided
    filters_dict = None
    if request.filters:
        filters_dict = request.filters.model_dump(exclude_none=True)

    try:
        result = await rag_service.aquery(
            query=request.query,
            context_limit=request.context_limit,
            filters=filters_dict
        )
        return RAGResponseModel(
            answer=result.answer,
            sources=result.sources,
            confidence=result.confidence,
            related_events=result.related_events,
            query_interpretation=result.query_interpretation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Agent API - Intelligent Query Processing
# ============================================================

class AgentRequest(BaseModel):
    """Request for agent-based intelligent processing."""
    query: str = Field(..., description="User query in any language")
    api_key: Optional[str] = Field(None, description="User's OpenAI API key (required)")
    language: str = Field("en", description="Response language: en, ko, ja")


class StructuredDataModel(BaseModel):
    """Structured data in response."""
    type: str
    items: Optional[List[Dict[str, Any]]] = None
    events: Optional[List[Dict[str, Any]]] = None
    chain: Optional[List[Dict[str, Any]]] = None
    markers: Optional[List[Dict[str, Any]]] = None
    cards: Optional[List[Dict[str, Any]]] = None
    comparison_axes: Optional[List[str]] = None


class AgentAnalysis(BaseModel):
    """Query analysis result."""
    original_query: str
    english_query: str
    intent: str
    intent_confidence: str
    entities: Dict[str, Any]
    response_format: str
    search_strategy: str
    requires_multiple_searches: bool


class AgentSearchResult(BaseModel):
    """Single search result."""
    query_used: str
    filters_applied: Dict[str, Any]
    results: List[Dict[str, Any]]
    result_count: int


class AgentResponseData(BaseModel):
    """Agent response data."""
    intent: str
    format: str
    answer: str
    structured_data: Dict[str, Any]
    sources: List[Dict[str, Any]]
    confidence: float
    suggested_followups: List[str]


class AgentResponse(BaseModel):
    """Full agent response including analysis and results."""
    analysis: AgentAnalysis
    search_results: List[AgentSearchResult]
    response: AgentResponseData


@router.post("/agent", response_model=AgentResponse)
async def agent_chat(request: AgentRequest):
    """
    Intelligent agent-based chat endpoint.

    - LOCAL DEV: Uses server's OPENAI_API_KEY env var if available
    - PRODUCTION: Requires user's own API key
    - NO KEY: Falls back to BM25 keyword search (free, limited)

    This endpoint uses the HistoryAgent which:
    1. Analyzes the query intent (comparison, timeline, causation, etc.)
    2. Extracts entities (events, persons, locations, time periods)
    3. Plans and executes appropriate searches
    4. Generates structured responses based on intent

    Example:
        POST /api/v1/chat/agent
        {"query": "마라톤 전투", "api_key": "sk-..."}  # Full AI
        {"query": "마라톤 전투"}  # BM25 fallback or local dev with env var
    """
    # Determine which API key to use
    api_key = request.api_key

    # In development, fallback to server's env var if no user key provided
    if not api_key:
        is_dev = os.getenv("CHALDEAS_ENV", "development") == "development"
        server_key = os.getenv("OPENAI_API_KEY")

        if is_dev and server_key:
            # Local development: use server's key
            api_key = server_key
            print("[SHEBA] Using server API key (development mode)")

    # If still no API key, use BM25 search fallback
    if not api_key:
        try:
            from app.services.hybrid_search import HybridSearchService

            bm25_service = HybridSearchService.get_instance()
            results = bm25_service.basic_search(request.query, limit=10)

            # Format BM25 results as agent response
            sources = [
                {"id": r["id"], "title": r["title"], "similarity": r["score"]}
                for r in results[:5]
            ]

            # Build simple answer from results
            if results:
                answer = f"'{request.query}' 검색 결과 {len(results)}건을 찾았습니다. AI 분석을 원하시면 OpenAI API 키를 입력해주세요."
            else:
                answer = f"'{request.query}'에 대한 검색 결과가 없습니다."

            return AgentResponse(
                analysis=AgentAnalysis(
                    original_query=request.query,
                    english_query=request.query,
                    intent="search",
                    intent_confidence="low",
                    entities={"keywords": [request.query]},
                    response_format="cards",
                    search_strategy="bm25_fallback",
                    requires_multiple_searches=False
                ),
                search_results=[AgentSearchResult(
                    query_used=request.query,
                    filters_applied={},
                    results=[{"content_type": "event", "content_id": r["id"], "content_text": r["title"], "metadata": r, "similarity": r["score"]} for r in results],
                    result_count=len(results)
                )],
                response=AgentResponseData(
                    intent="search",
                    format="cards",
                    answer=answer,
                    structured_data={"type": "cards", "cards": [{"title": r["title"], "content": r.get("description", "")[:200] if r.get("description") else "", "subtitle": f"{abs(r.get('date_start', 0))} {'BCE' if r.get('date_start', 0) < 0 else 'CE'}"} for r in results[:5]]},
                    sources=sources,
                    confidence=0.5,
                    suggested_followups=[]
                )
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"BM25 search failed: {str(e)}")

    # Validate API key format
    if not api_key.startswith("sk-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid API key format. OpenAI API keys start with 'sk-'."
        )

    try:
        # Create a new agent instance with the determined API key
        from app.core.sheba.history_agent import HistoryAgent
        from app.services.rag_service import RAGService

        # Create RAG service with key
        user_rag_service = RAGService(api_key=api_key)

        # Create agent with key
        user_agent = HistoryAgent(
            rag_service=user_rag_service,
            api_key=api_key
        )

        result = user_agent.process(request.query, language=request.language)

        return AgentResponse(
            analysis=AgentAnalysis(**result["analysis"]),
            search_results=[AgentSearchResult(**sr) for sr in result["search_results"]],
            response=AgentResponseData(**result["response"])
        )
    except Exception as e:
        # Check for API key errors
        error_str = str(e).lower()
        if "api key" in error_str or "authentication" in error_str or "unauthorized" in error_str:
            raise HTTPException(
                status_code=401,
                detail="Invalid OpenAI API key. Please check your API key and try again."
            )
        raise HTTPException(status_code=500, detail=str(e))
