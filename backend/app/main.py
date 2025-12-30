"""
CHALDEAS - Main FastAPI Application

The entry point for the Chaldeas historical knowledge system.
Implements World-Centric Architecture with FGO-inspired naming.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.router import api_router

settings = get_settings()

app = FastAPI(
    title=settings.project_name,
    description="""
    CHALDEAS: World-Centric Historical Knowledge System

    A system for exploring world history, philosophy, science, mythology,
    and biographical information across time and space.

    ## Systems

    - **CHALDEAS**: World state management (immutable snapshots)
    - **SHEBA**: Observation and query processing
    - **LAPLACE**: Explanation and source attribution
    - **TRISMEGISTUS**: System orchestration
    - **PAPERMOON**: Proposal verification
    - **LOGOS**: LLM-based action proposer
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint - system status."""
    return {
        "system": "CHALDEAS",
        "status": "operational",
        "version": "0.1.0",
        "subsystems": {
            "chaldeas": "online",  # World state
            "sheba": "standby",    # Observer
            "laplace": "standby",  # Explainer
            "trismegistus": "online",  # Orchestrator
            "papermoon": "standby",    # Authority
            "logos": "standby",        # Actor
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
