"""
Chat schemas for SHEBA conversational interface.
"""
from pydantic import BaseModel
from typing import Optional, Any

from app.schemas.event import Event
from app.schemas.source import Source


class ChatContext(BaseModel):
    """Optional context for chat queries."""
    year: Optional[int] = None
    location: Optional[str] = None
    category: Optional[str] = None
    previous_topics: list[str] = []


class ChatRequest(BaseModel):
    """Request to SHEBA chat interface."""
    query: str
    context: Optional[ChatContext] = None
    language: str = "en"  # Response language


class ExplanationSource(BaseModel):
    """Source with explanation from LAPLACE."""
    source: Source
    relevance: float  # How relevant this source is to the answer
    excerpt: Optional[str] = None


class ChatResponse(BaseModel):
    """
    Response from SHEBA/LOGOS/LAPLACE pipeline.

    Includes:
    - Natural language answer (LOGOS)
    - Sources and explanations (LAPLACE)
    - Related data for exploration
    """
    answer: str
    sources: list[ExplanationSource] = []
    confidence: float  # How confident the system is in this answer
    related_events: list[Event] = []
    suggested_queries: list[str] = []  # Follow-up questions

    # Internal tracking (for PAPERMOON audit)
    proposal_id: Optional[str] = None
    reasoning_trace: Optional[dict[str, Any]] = None
