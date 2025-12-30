"""
SHEBA Chat API endpoints.

Provides conversational interface to the historical knowledge system.
This is where SHEBA (observation) + LOGOS (proposal) + LAPLACE (explanation)
come together.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.trismegistus.orchestrator import Orchestrator

router = APIRouter()


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
