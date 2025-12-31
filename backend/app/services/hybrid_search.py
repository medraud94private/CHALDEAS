"""
Hybrid Search Service - BM25 + Vector Search

일반검색: BM25 키워드 매칭 (무료, 비공개)
고급검색: BM25 + Vector + AI (마스터 기록 공개)
"""
import re
import math
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """검색 결과"""
    id: str
    title: str
    description: str
    score: float
    date_start: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: Optional[str] = None
    source_type: str = "event"  # event, person, location
    metadata: Dict[str, Any] = field(default_factory=dict)


class BM25Index:
    """
    BM25 인덱스 (메모리 기반)

    PostgreSQL의 tsvector 대신 메모리에서 BM25 구현
    향후 pg_search로 전환 가능
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # 용어 빈도 포화 파라미터
        self.b = b    # 문서 길이 정규화 파라미터

        self.documents: List[Dict] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0
        self.doc_freqs: Dict[str, int] = Counter()  # 각 단어가 등장한 문서 수
        self.inverted_index: Dict[str, List[Tuple[int, int]]] = {}  # word -> [(doc_id, freq), ...]
        self.vocab: set = set()

    def tokenize(self, text: str) -> List[str]:
        """토큰화 (영어/한국어/일본어 지원)"""
        if not text:
            return []

        # 소문자 변환
        text = text.lower()

        # 영어: 단어 단위
        # 한국어/일본어: 문자 n-gram (2-gram)
        tokens = []

        # 영어 단어 추출
        english_words = re.findall(r'[a-z]+', text)
        tokens.extend(english_words)

        # 한국어 추출 (자모 분리 없이 음절 단위)
        korean_chars = re.findall(r'[\uac00-\ud7af]+', text)
        for word in korean_chars:
            if len(word) >= 2:
                # 2-gram
                for i in range(len(word) - 1):
                    tokens.append(word[i:i+2])
            if len(word) >= 1:
                tokens.append(word)  # 전체 단어도 추가

        # 일본어 추출 (히라가나, 카타카나, 한자)
        japanese_chars = re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+', text)
        for word in japanese_chars:
            if len(word) >= 2:
                for i in range(len(word) - 1):
                    tokens.append(word[i:i+2])
            if len(word) >= 1:
                tokens.append(word)

        return tokens

    def build(self, documents: List[Dict], text_fields: List[str] = None):
        """인덱스 빌드"""
        if text_fields is None:
            text_fields = ["title", "description", "name"]

        self.documents = documents
        self.doc_lengths = []
        self.doc_freqs = Counter()
        self.inverted_index = {}
        self.vocab = set()

        for doc_id, doc in enumerate(documents):
            # 모든 텍스트 필드 합치기
            combined_text = " ".join(
                str(doc.get(field, "")) for field in text_fields
            )

            tokens = self.tokenize(combined_text)
            self.doc_lengths.append(len(tokens))

            # 단어 빈도 계산
            term_freqs = Counter(tokens)

            # 역인덱스 및 문서 빈도 업데이트
            for term, freq in term_freqs.items():
                self.vocab.add(term)

                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append((doc_id, freq))

                self.doc_freqs[term] += 1

        # 평균 문서 길이
        if self.doc_lengths:
            self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)
        else:
            self.avg_doc_length = 0

    def search(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        """BM25 검색"""
        if not self.documents:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * len(self.documents)
        N = len(self.documents)

        for term in query_tokens:
            if term not in self.inverted_index:
                continue

            # IDF 계산
            df = self.doc_freqs[term]
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1)

            # 각 문서의 점수 계산
            for doc_id, tf in self.inverted_index[term]:
                doc_len = self.doc_lengths[doc_id]

                # BM25 공식
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)

                scores[doc_id] += idf * (numerator / denominator)

        # 상위 K개 결과
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(doc_id, score) for doc_id, score in ranked[:top_k] if score > 0]


class HybridSearchService:
    """
    하이브리드 검색 서비스

    - basic_search: BM25 키워드 검색만
    - advanced_search: BM25 + Vector + AI
    """

    def __init__(self, rag_service=None):
        self.rag_service = rag_service

        # BM25 인덱스들
        self.event_index = BM25Index()
        self.person_index = BM25Index()
        self.location_index = BM25Index()

        # 데이터 캐시
        self._events = None
        self._persons = None
        self._locations = None
        self._indexed = False

    def _load_and_index(self):
        """데이터 로드 및 인덱싱"""
        if self._indexed:
            return

        from app.services.json_data import get_data_service
        data_service = get_data_service()

        self._events = data_service.events
        self._persons = data_service.persons
        self._locations = data_service.locations

        # BM25 인덱스 빌드
        self.event_index.build(
            self._events,
            text_fields=["title", "title_ko", "description"]
        )
        self.person_index.build(
            self._persons,
            text_fields=["name", "name_ko", "biography", "description"]
        )
        self.location_index.build(
            self._locations,
            text_fields=["name", "name_ko", "modern_name", "description"]
        )

        self._indexed = True
        print(f"[HybridSearch] Indexed {len(self._events)} events, "
              f"{len(self._persons)} persons, {len(self._locations)} locations")

    def basic_search(
        self,
        query: str,
        limit: int = 20,
        type_filter: Optional[str] = None  # event, person, location, all
    ) -> Dict[str, Any]:
        """
        일반검색 - BM25 키워드 매칭

        무료, 비공개, AI 없음
        """
        self._load_and_index()

        results = {
            "query": query,
            "search_type": "basic",
            "events": [],
            "persons": [],
            "locations": [],
            "total": 0
        }

        # 이벤트 검색
        if type_filter in (None, "all", "event"):
            event_hits = self.event_index.search(query, top_k=limit)
            for doc_id, score in event_hits:
                doc = self._events[doc_id]
                results["events"].append({
                    **doc,
                    "bm25_score": score,
                    "source_type": "event"
                })

        # 인물 검색
        if type_filter in (None, "all", "person"):
            person_hits = self.person_index.search(query, top_k=limit)
            for doc_id, score in person_hits:
                doc = self._persons[doc_id]
                results["persons"].append({
                    **doc,
                    "bm25_score": score,
                    "source_type": "person"
                })

        # 장소 검색
        if type_filter in (None, "all", "location"):
            location_hits = self.location_index.search(query, top_k=limit)
            for doc_id, score in location_hits:
                doc = self._locations[doc_id]
                results["locations"].append({
                    **doc,
                    "bm25_score": score,
                    "source_type": "location"
                })

        results["total"] = (
            len(results["events"]) +
            len(results["persons"]) +
            len(results["locations"])
        )

        return results

    async def advanced_search(
        self,
        query: str,
        limit: int = 10,
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """
        고급검색 - BM25 + Vector + AI

        마스터 기록 공개, AI 응답 생성
        """
        self._load_and_index()

        # 1단계: BM25로 후보 추출
        bm25_results = self.basic_search(query, limit=limit * 2)

        # 2단계: Vector 검색 (RAG 서비스 사용)
        vector_results = []
        if self.rag_service:
            try:
                rag_response = await self.rag_service.aquery(
                    query=query,
                    context_limit=limit
                )
                vector_results = rag_response.sources if hasattr(rag_response, 'sources') else []
            except Exception as e:
                print(f"[HybridSearch] Vector search failed: {e}")

        # 3단계: RRF (Reciprocal Rank Fusion) 점수 결합
        combined_results = self._fuse_results(
            bm25_results["events"],
            vector_results,
            limit=limit
        )

        result = {
            "query": query,
            "search_type": "advanced",
            "results": combined_results,
            "bm25_count": len(bm25_results["events"]),
            "vector_count": len(vector_results),
            "total": len(combined_results)
        }

        # 4단계: AI 응답 (선택적)
        if use_ai and self.rag_service:
            try:
                rag_response = await self.rag_service.aquery(
                    query=query,
                    context_limit=limit
                )
                result["ai_response"] = {
                    "answer": rag_response.answer,
                    "confidence": rag_response.confidence,
                    "related_events": rag_response.related_events
                }
            except Exception as e:
                result["ai_response"] = {"error": str(e)}

        return result

    def _fuse_results(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        limit: int = 10,
        k: int = 60  # RRF 상수
    ) -> List[Dict]:
        """
        RRF (Reciprocal Rank Fusion)로 결과 결합

        RRF(d) = Σ 1 / (k + rank_i(d))
        """
        scores = {}
        result_map = {}

        # BM25 결과 점수
        for rank, doc in enumerate(bm25_results):
            doc_id = doc.get("id", str(hash(doc.get("title", ""))))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            result_map[doc_id] = doc

        # Vector 결과 점수
        for rank, doc in enumerate(vector_results):
            doc_id = doc.get("id", str(hash(doc.get("title", ""))))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            if doc_id not in result_map:
                result_map[doc_id] = doc

        # 점수순 정렬
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids[:limit]:
            doc = result_map[doc_id].copy()
            doc["rrf_score"] = scores[doc_id]
            results.append(doc)

        return results


# 싱글턴 인스턴스
_hybrid_search_service = None


def get_hybrid_search_service(rag_service=None) -> HybridSearchService:
    """Get or create hybrid search service instance."""
    global _hybrid_search_service
    if _hybrid_search_service is None:
        _hybrid_search_service = HybridSearchService(rag_service=rag_service)
    return _hybrid_search_service
