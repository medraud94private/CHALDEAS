# CHALDEAS V1 API
# Historical Chain 기반 신규 API 엔드포인트

from fastapi import APIRouter
from . import explore

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Explore: 큐레이션 전 엔티티 탐색
router.include_router(explore.router)

# TODO: 라우터 등록은 각 모듈 구현 후 추가
# from .curation import router as curation_router
# from .periods import router as periods_router
# router.include_router(curation_router)
# router.include_router(periods_router)
