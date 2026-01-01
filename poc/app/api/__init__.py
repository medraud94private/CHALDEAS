"""
CHALDEAS V1 PoC API Routes
"""
from fastapi import APIRouter

from .chains import router as chains_router
from .entities import router as entities_router

router = APIRouter()

# Include sub-routers
router.include_router(chains_router, prefix="/chains", tags=["chains"])
router.include_router(entities_router, prefix="/entities", tags=["entities"])
