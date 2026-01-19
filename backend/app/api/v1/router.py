"""
API v1 Router - Aggregates all API endpoints.
"""
from fastapi import APIRouter

from app.api.v1 import events, locations, search, chat, categories, showcases, story
from app.api.v1_new import explore, globe

api_router = APIRouter()

# Data endpoints
api_router.include_router(events.router, prefix="/events", tags=["Events"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])

# Categories (Singularities, Lostbelts)
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])

# Showcase/Archive endpoints (FGO + Pan-Human History)
api_router.include_router(showcases.router, prefix="/showcases", tags=["Showcases"])

# Search endpoints (Basic/Advanced)
api_router.include_router(search.router, prefix="/search", tags=["Search"])

# Chat/RAG endpoints (SHEBA + LOGOS)
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

# V1 New: Explore pre-curation entity pool
api_router.include_router(explore.router, tags=["Explore"])

# V1 New: Globe markers and connections
api_router.include_router(globe.router, tags=["Globe"])

# Story endpoints (Person/Place/Arc Story)
api_router.include_router(story.router, prefix="/story", tags=["Story"])
