"""
Master System - 마스터 및 검색 기록 관리

FGO 컨셉:
- 각 유저는 마스터 번호를 부여받음
- 고급검색(AI) 사용 시 검색 기록이 공개됨
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Master(Base):
    """마스터 (유저) 모델"""
    __tablename__ = "masters"

    id = Column(Integer, primary_key=True, index=True)

    # 마스터 번호 (공개용, 예: #001, #042)
    master_number = Column(Integer, unique=True, nullable=False, index=True)

    # 선택적 닉네임
    nickname = Column(String(50))

    # 인증 (나중에 확장)
    session_token = Column(String(255), unique=True, index=True)

    # 통계
    basic_search_count = Column(Integer, default=0)
    advanced_search_count = Column(Integer, default=0)

    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 검색 기록 관계
    search_logs = relationship("SearchLog", back_populates="master")


class SearchLog(Base):
    """검색 기록 (고급검색만 공개)"""
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)

    # 마스터 참조
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    master = relationship("Master", back_populates="search_logs")

    # 검색 정보
    query = Column(Text, nullable=False)
    query_language = Column(String(10), default="ko")  # ko, ja, en
    search_type = Column(String(20), nullable=False)  # basic, advanced

    # AI 응답 (고급검색만)
    response_summary = Column(Text)  # 응답 요약
    intent = Column(String(50))  # comparison, timeline, causation, etc.

    # 관련 이벤트 (발견된 것들)
    related_event_ids = Column(Text)  # comma-separated

    # 공개 여부 (고급검색은 기본 공개)
    is_public = Column(Boolean, default=False)

    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 마스터 번호 자동 생성 함수
def generate_master_number(db) -> int:
    """다음 마스터 번호 생성"""
    from sqlalchemy import func as sql_func
    max_num = db.query(sql_func.max(Master.master_number)).scalar()
    return (max_num or 0) + 1
