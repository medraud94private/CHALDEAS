"""
Master Service - 마스터 관리 및 검색 기록

FGO 컨셉:
- 고급검색 시 마스터 번호 부여
- 검색 기록 공개 (칼데아 아카이브)
"""
import secrets
from typing import Optional, List, Dict, Any
from datetime import datetime


class MasterService:
    """
    마스터 관리 서비스 (메모리 기반)

    향후 PostgreSQL로 전환 예정
    """

    def __init__(self):
        self._masters: Dict[str, Dict] = {}  # session_token -> master
        self._search_logs: List[Dict] = []
        self._next_master_number = 1

    def get_or_create_master(self, session_token: Optional[str] = None) -> Dict:
        """
        세션 토큰으로 마스터 조회 또는 생성

        Returns:
            {
                "master_number": 42,
                "session_token": "xxx",
                "nickname": None,
                "basic_search_count": 0,
                "advanced_search_count": 0,
                "created_at": "2024-01-01T00:00:00"
            }
        """
        if session_token and session_token in self._masters:
            return self._masters[session_token]

        # 새 마스터 생성
        new_token = session_token or secrets.token_urlsafe(32)
        master = {
            "master_number": self._next_master_number,
            "session_token": new_token,
            "nickname": None,
            "basic_search_count": 0,
            "advanced_search_count": 0,
            "created_at": datetime.now().isoformat(),
            "last_active_at": datetime.now().isoformat()
        }

        self._masters[new_token] = master
        self._next_master_number += 1

        return master

    def get_master_by_number(self, master_number: int) -> Optional[Dict]:
        """마스터 번호로 조회"""
        for master in self._masters.values():
            if master["master_number"] == master_number:
                return master
        return None

    def increment_search_count(
        self,
        session_token: str,
        search_type: str  # "basic" or "advanced"
    ):
        """검색 카운트 증가"""
        if session_token in self._masters:
            master = self._masters[session_token]
            if search_type == "basic":
                master["basic_search_count"] += 1
            else:
                master["advanced_search_count"] += 1
            master["last_active_at"] = datetime.now().isoformat()

    def log_search(
        self,
        master_number: int,
        query: str,
        search_type: str,
        query_language: str = "ko",
        response_summary: Optional[str] = None,
        intent: Optional[str] = None,
        related_event_ids: Optional[List[str]] = None,
        is_public: bool = True
    ) -> Dict:
        """
        검색 기록 저장

        고급검색은 기본 공개
        """
        log_entry = {
            "id": len(self._search_logs) + 1,
            "master_number": master_number,
            "query": query,
            "query_language": query_language,
            "search_type": search_type,
            "response_summary": response_summary,
            "intent": intent,
            "related_event_ids": related_event_ids or [],
            "is_public": is_public,
            "created_at": datetime.now().isoformat()
        }

        self._search_logs.append(log_entry)
        return log_entry

    def get_public_search_logs(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """공개된 검색 기록 조회 (고급검색만)"""
        public_logs = [
            log for log in self._search_logs
            if log["is_public"] and log["search_type"] == "advanced"
        ]

        # 최신순 정렬
        public_logs.sort(key=lambda x: x["created_at"], reverse=True)

        return public_logs[offset:offset + limit]

    def get_master_search_history(
        self,
        master_number: int,
        include_private: bool = False
    ) -> List[Dict]:
        """특정 마스터의 검색 기록"""
        logs = [
            log for log in self._search_logs
            if log["master_number"] == master_number
        ]

        if not include_private:
            logs = [log for log in logs if log["is_public"]]

        logs.sort(key=lambda x: x["created_at"], reverse=True)
        return logs

    def get_stats(self) -> Dict[str, Any]:
        """통계"""
        return {
            "total_masters": len(self._masters),
            "total_searches": len(self._search_logs),
            "public_searches": sum(1 for log in self._search_logs if log["is_public"]),
            "advanced_searches": sum(1 for log in self._search_logs if log["search_type"] == "advanced")
        }


# 싱글턴 인스턴스
_master_service = None


def get_master_service() -> MasterService:
    """Get or create master service instance."""
    global _master_service
    if _master_service is None:
        _master_service = MasterService()
    return _master_service
