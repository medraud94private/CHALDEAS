# CHALDEAS V1 Schemas
# Pydantic 스키마 정의

from .period import (
    PeriodBase,
    Period,
    PeriodCreate,
    PeriodUpdate,
    PeriodWithChildren,
    PeriodList,
    TemporalScale,
)

# 아직 구현되지 않은 스키마들 (CP-2.1, CP-3.1에서 추가 예정)
# from .chain import ChainBase, HistoricalChain, ChainSegment, CurationRequest, CurationResponse
# from .text_mention import TextSourceBase, TextSource, TextMention

__all__ = [
    "PeriodBase",
    "Period",
    "PeriodCreate",
    "PeriodUpdate",
    "PeriodWithChildren",
    "PeriodList",
    "TemporalScale",
]
