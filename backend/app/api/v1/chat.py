"""
SHEBA Chat API endpoints.

Provides conversational interface to the historical knowledge system.
This is where SHEBA (observation) + LOGOS (proposal) + LAPLACE (explanation)
come together.
"""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.trismegistus.orchestrator import Orchestrator

router = APIRouter()

# RAG Service (lazy initialization)
_rag_service = None

def get_rag_service():
    """Get or create RAG service instance."""
    global _rag_service
    if _rag_service is None:
        try:
            from app.services.rag_service import RAGService
            _rag_service = RAGService()
        except Exception as e:
            print(f"Warning: RAG service not available: {e}")
            return None
    return _rag_service


class RAGRequest(BaseModel):
    """Request for RAG-based chat."""
    query: str
    context_limit: int = 5


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
    """
    rag_service = get_rag_service()

    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG service not available. Check if pgvector is running and events are indexed."
        )

    try:
        result = await rag_service.aquery(
            query=request.query,
            context_limit=request.context_limit
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
