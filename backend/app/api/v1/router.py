"""
API v1 Router - Aggregates all API endpoints.
"""
from fastapi import APIRouter

from app.api.v1 import events, locations, search, chat

api_router = APIRouter()

# Data endpoints
api_router.include_router(events.router, prefix="/events", tags=["Events"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])

# Search endpoints
api_router.include_router(search.router, prefix="/search", tags=["Search"])

# Chat/RAG endpoints (SHEBA + LOGOS)
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
