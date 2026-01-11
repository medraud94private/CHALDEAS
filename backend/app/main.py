"""
CHALDEAS - Main FastAPI Application

The entry point for the Chaldeas historical knowledge system.
Implements World-Centric Architecture with FGO-inspired naming.
"""
# Load environment variables first
from dotenv import load_dotenv
load_dotenv("../.env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
from app.api.v1.router import api_router
from app.api.v1_new import router as v1_new_router

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

# Include API routers
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(v1_new_router)  # V1 New (Historical Chain) - already has /api/v1 prefix


# ============== Global Exception Handlers ==============

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error occurred", "type": "database_error"}
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors (duplicates, FK violations)."""
    logger.warning(f"Integrity error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"detail": "Data conflict - duplicate or invalid reference", "type": "integrity_error"}
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "type": "validation_error"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": "internal_error"}
    )


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
