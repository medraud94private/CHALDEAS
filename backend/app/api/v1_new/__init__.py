# CHALDEAS V1 API
# Historical Chain 기반 신규 API 엔드포인트

from fastapi import APIRouter
from . import explore
from . import globe
from . import stats
from . import chains

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Explore: 큐레이션 전 엔티티 탐색
router.include_router(explore.router)

# Globe: 3D 지구본 마커 및 연결
router.include_router(globe.router)

# Stats: 데이터베이스 통계
router.include_router(stats.router)

# Chains: 이벤트 연결 그래프 (Historical Chain)
router.include_router(chains.router)
