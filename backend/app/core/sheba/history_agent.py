"""
SHEBA History Agent - 역사 질의 처리 에이전트

다단계 사고 과정:
1. 쿼리 분석 (의도, 엔티티 추출)
2. 검색 전략 수립
3. 검색 실행
4. 응답 생성
5. 정합성 검증
"""

import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from openai import OpenAI
import os


class QueryIntent(str, Enum):
    """쿼리 의도 분류"""
    COMPARISON = "comparison"       # 비교: "A와 B 비교해줘"
    TIMELINE = "timeline"           # 연대기: "~의 흐름/전개"
    CAUSATION = "causation"         # 인과관계: "왜 ~했어?", "~의 원인/결과"
    DEEP_DIVE = "deep_dive"         # 상세설명: "~에 대해 자세히"
    OVERVIEW = "overview"           # 개요: "~이 뭐야?", "간단히 설명해줘"
    MAP_QUERY = "map_query"         # 지도: "~는 어디야?", "~의 위치"
    PERSON_INFO = "person_info"     # 인물: "~는 누구야?"
    CONNECTION = "connection"       # 연결고리: "~와 ~의 관계"


class ResponseFormat(str, Enum):
    """응답 형식"""
    NARRATIVE = "narrative"         # 서술형 텍스트
    COMPARISON_TABLE = "comparison_table"  # 비교 테이블
    TIMELINE_LIST = "timeline_list" # 시간순 리스트
    FLOW_CHART = "flow_chart"       # 인과관계 플로우
    MAP_MARKERS = "map_markers"     # 지도 마커
    CARDS = "cards"                 # 카드형 요약


@dataclass
class ExtractedEntities:
    """추출된 엔티티"""
    events: List[str]           # 이벤트명
    persons: List[str]          # 인물명
    locations: List[str]        # 장소명
    time_periods: List[Dict]    # 시대 {"from": -500, "to": 0, "label": "고대"}
    categories: List[str]       # 카테고리 (battle, treaty, etc.)
    keywords: List[str]         # 기타 키워드


@dataclass
class QueryAnalysis:
    """쿼리 분석 결과"""
    original_query: str
    english_query: str
    intent: QueryIntent
    intent_confidence: str      # high, medium, low
    entities: ExtractedEntities
    response_format: ResponseFormat
    search_strategy: str        # 검색 전략 설명
    requires_multiple_searches: bool


@dataclass
class SearchResult:
    """검색 결과"""
    query_used: str
    filters_applied: Dict
    results: List[Dict]
    result_count: int


@dataclass
class StructuredResponse:
    """구조화된 응답"""
    intent: str
    format: str
    answer: str
    structured_data: Dict[str, Any]
    sources: List[Dict]
    confidence: float
    suggested_followups: List[str]
    navigation: Optional[Dict[str, Any]] = field(default=None)


class HistoryAgent:
    """
    SHEBA 역사 에이전트

    Flow:
    1. analyze_query() - 쿼리 의도/엔티티 분석
    2. plan_search() - 검색 전략 수립
    3. execute_search() - 검색 실행
    4. generate_response() - 응답 생성
    5. validate_response() - 정합성 검증
    """

    ANALYSIS_PROMPT = """당신은 역사 질의 분석 전문가입니다.
사용자의 질문을 분석하여 JSON 형식으로 출력하세요.

## 분석 항목

### 1. intent (의도)
- comparison: 두 가지 이상 비교 ("A와 B 비교", "차이점")
- timeline: 시간순 흐름 ("전개", "흐름", "과정")
- causation: 원인/결과 ("왜", "때문에", "영향", "결과")
- deep_dive: 상세 설명 ("자세히", "구체적으로")
- overview: 간단한 개요 ("뭐야", "간단히", "소개")
- map_query: 위치 관련 ("어디", "위치", "장소")
- person_info: 인물 정보 ("누구", 인물명 질문)
- connection: 관계/연결 ("관계", "연결", "사이")

### 2. entities (추출할 것들)
- events: 언급된 역사적 사건명
- persons: 언급된 인물명
- locations: 언급된 장소명
- time_periods: 언급된 시대 (from/to는 정수, BCE는 음수)
- categories: 추론되는 카테고리 (battle, war, treaty, discovery, etc.)
- keywords: 검색에 사용할 영어 키워드

### 3. response_format (적절한 응답 형식)
- narrative: 서술형 (기본)
- comparison_table: 비교표 (comparison일 때)
- timeline_list: 연대기 (timeline일 때)
- flow_chart: 인과관계도 (causation일 때)
- map_markers: 지도 표시 (map_query일 때)
- cards: 카드형 (overview, person_info일 때)

### 4. search_strategy
어떻게 검색할지 한 문장으로 설명

### 5. requires_multiple_searches
여러 번 검색이 필요한지 (true/false)

## 출력 형식 (JSON만 출력)
```json
{
  "english_query": "영어로 번역된 검색 쿼리",
  "intent": "의도",
  "intent_confidence": "high|medium|low",
  "entities": {
    "events": [],
    "persons": [],
    "locations": [],
    "time_periods": [{"from": -500, "to": 0, "label": "고대 그리스"}],
    "categories": [],
    "keywords": []
  },
  "response_format": "형식",
  "search_strategy": "전략 설명",
  "requires_multiple_searches": false
}
```"""

    RESPONSE_PROMPT = """당신은 CHALDEAS 역사 해설 AI입니다.

## 핵심 원칙
역사는 **연결된 이야기**입니다. "왜?", "그래서?"를 항상 설명하세요.

## 스타일
- 인과관계 중심 설명
- 구어체 ("~했거든", "~였는데", "ㄹㅇ" OK)
- 구체적 숫자/사례 사용
- 의외의 연결고리, 재미있는 뒷이야기 포함

## 응답 형식: {response_format}

{format_instructions}

## 검색된 컨텍스트
{context}

## 사용자 질문
{query}

## 출력 (JSON)
```json
{{
  "answer": "답변 텍스트",
  "structured_data": {structured_data_template},
  "suggested_followups": ["후속 질문 1", "후속 질문 2"]
}}
```"""

    FORMAT_INSTRUCTIONS = {
        "narrative": "서술형으로 자연스럽게 설명하세요.",
        "comparison_table": """비교표 형식으로 structured_data를 채우세요:
{
  "type": "comparison",
  "items": [
    {"title": "항목1", "date": "날짜", "key_points": ["포인트1", ...]},
    {"title": "항목2", "date": "날짜", "key_points": ["포인트1", ...]}
  ],
  "comparison_axes": ["비교축1", "비교축2", ...]
}""",
        "timeline_list": """시간순 리스트로 structured_data를 채우세요:
{
  "type": "timeline",
  "events": [
    {"date": "날짜", "title": "제목", "description": "설명"},
    ...
  ]
}""",
        "flow_chart": """인과관계 플로우로 structured_data를 채우세요:
{
  "type": "causation",
  "chain": [
    {"cause": "원인", "effect": "결과", "explanation": "설명"},
    ...
  ]
}""",
        "map_markers": """지도 마커로 structured_data를 채우세요:
{
  "type": "map",
  "markers": [
    {"title": "제목", "lat": 위도, "lng": 경도, "description": "설명"},
    ...
  ]
}""",
        "cards": """카드형으로 structured_data를 채우세요:
{
  "type": "cards",
  "cards": [
    {"title": "제목", "subtitle": "부제", "content": "내용", "tags": ["태그1"]},
    ...
  ]
}"""
    }

    def __init__(
        self,
        rag_service=None,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.rag_service = rag_service

    def analyze_query(self, query: str) -> QueryAnalysis:
        """1단계: 쿼리 분석"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.ANALYSIS_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        entities = ExtractedEntities(
            events=result.get("entities", {}).get("events", []),
            persons=result.get("entities", {}).get("persons", []),
            locations=result.get("entities", {}).get("locations", []),
            time_periods=result.get("entities", {}).get("time_periods", []),
            categories=result.get("entities", {}).get("categories", []),
            keywords=result.get("entities", {}).get("keywords", [])
        )

        return QueryAnalysis(
            original_query=query,
            english_query=result.get("english_query", query),
            intent=QueryIntent(result.get("intent", "overview")),
            intent_confidence=result.get("intent_confidence", "medium"),
            entities=entities,
            response_format=ResponseFormat(result.get("response_format", "narrative")),
            search_strategy=result.get("search_strategy", ""),
            requires_multiple_searches=result.get("requires_multiple_searches", False)
        )

    def execute_search(self, analysis: QueryAnalysis) -> List[SearchResult]:
        """2단계: 검색 실행"""
        if not self.rag_service:
            return []

        results = []

        # 기본 검색
        filters = {}

        # 시대 필터 적용
        if analysis.entities.time_periods:
            tp = analysis.entities.time_periods[0]
            if tp.get("from") is not None:
                filters["date_from"] = tp["from"]
            if tp.get("to") is not None:
                filters["date_to"] = tp["to"]

        # 카테고리 필터 적용
        if analysis.entities.categories:
            filters["category"] = analysis.entities.categories[0]

        # 비교 의도일 때: 각 항목별 검색
        if analysis.intent == QueryIntent.COMPARISON and analysis.entities.events:
            for event in analysis.entities.events[:2]:  # 최대 2개
                context = self.rag_service.retrieve_context(
                    event,
                    limit=10,  # 3 → 10 (더 많이 가져온 후 필터링)
                    filters=filters if filters else None
                )
                results.append(SearchResult(
                    query_used=event,
                    filters_applied=filters,
                    results=context,
                    result_count=len(context)
                ))
        else:
            # 일반 검색
            context = self.rag_service.retrieve_context(
                analysis.english_query,
                limit=20,  # 5 → 20 (더 많이 가져온 후 필터링)
                filters=filters if filters else None
            )
            results.append(SearchResult(
                query_used=analysis.english_query,
                filters_applied=filters,
                results=context,
                result_count=len(context)
            ))

        return results

    def filter_relevant_results(self, query: str, search_results: List[SearchResult]) -> List[SearchResult]:
        """에이전트가 검색 결과를 읽고 관련있는 것만 필터링 (수치만으로 판단X)"""
        if not search_results or not search_results[0].results:
            return search_results

        all_results = []
        for sr in search_results:
            for doc in sr.results:
                text = doc.get("content_text", "")
                meta = doc.get("metadata", {})
                all_results.append({
                    "index": len(all_results),
                    "title": meta.get("title", "Unknown"),
                    "text": text[:500],
                    "doc": doc
                })

        if not all_results:
            return search_results

        filter_prompt = f"""검색 결과 관련성 판단. 질문: {query}

관련있는 것만 선택 (최대 5~7개). 키워드만 포함되어도 관련없을 수 있음.

"""
        for r in all_results[:15]:
            filter_prompt += f"[{r['index']}] {r['title']}: {r['text'][:200]}...\n"
        filter_prompt += '\nJSON: {"relevant_indices": [0, 2], "reasoning": "이유"}'

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": filter_prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            relevant_indices = set(result.get("relevant_indices", []))
            print(f"[SHEBA] Filtered: {len(relevant_indices)}/{len(all_results)}")

            if not relevant_indices:
                relevant_indices = set(range(min(3, len(all_results))))

            filtered_docs = [all_results[i]["doc"] for i in sorted(relevant_indices) if i < len(all_results)]
            if filtered_docs:
                return [SearchResult(
                    query_used=search_results[0].query_used,
                    filters_applied=search_results[0].filters_applied,
                    results=filtered_docs,
                    result_count=len(filtered_docs)
                )]
            return search_results
        except Exception as e:
            print(f"[SHEBA] Filter error: {e}")
            return search_results

    def generate_response(
        self,
        analysis: QueryAnalysis,
        search_results: List[SearchResult]
    ) -> StructuredResponse:
        """3단계: 응답 생성"""

        # 컨텍스트 구성
        context_parts = []
        all_sources = []

        for sr in search_results:
            for i, doc in enumerate(sr.results):
                text = doc.get("content_text", "")
                meta = doc.get("metadata", {})
                context_parts.append(f"[{len(context_parts)+1}] {text}")
                all_sources.append({
                    "id": doc.get("content_id"),
                    "title": meta.get("title", ""),
                    "similarity": doc.get("similarity", 0),
                    "date_start": meta.get("date_start"),
                    "latitude": meta.get("latitude"),
                    "longitude": meta.get("longitude"),
                })

        context_str = "\n\n".join(context_parts) if context_parts else "관련 데이터 없음"

        # 응답 형식별 지침
        format_key = analysis.response_format.value
        format_instructions = self.FORMAT_INSTRUCTIONS.get(format_key, "")

        # 구조화 데이터 템플릿
        structured_templates = {
            "narrative": "{}",
            "comparison_table": '{"type": "comparison", "items": [], "comparison_axes": []}',
            "timeline_list": '{"type": "timeline", "events": []}',
            "flow_chart": '{"type": "causation", "chain": []}',
            "map_markers": '{"type": "map", "markers": []}',
            "cards": '{"type": "cards", "cards": []}'
        }

        prompt = self.RESPONSE_PROMPT.format(
            response_format=format_key,
            format_instructions=format_instructions,
            context=context_str,
            query=analysis.original_query,
            structured_data_template=structured_templates.get(format_key, "{}")
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # confidence 계산
        max_sim = max([s["similarity"] for s in all_sources]) if all_sources else 0

        # navigation 데이터 추출
        navigation = result.get("navigation", {})
        if not navigation.get("target_year") and all_sources:
            for src in all_sources:
                if src.get("date_start"):
                    navigation["target_year"] = src["date_start"]
                    break

        if not navigation.get("locations") and all_sources:
            locs = [{"title": s["title"], "lat": s["latitude"], "lng": s["longitude"], "year": s.get("date_start")}
                    for s in all_sources if s.get("latitude") and s.get("longitude")][:5]
            if locs:
                navigation["locations"] = locs

        return StructuredResponse(
            intent=analysis.intent.value,
            format=analysis.response_format.value,
            answer=result.get("answer", ""),
            structured_data=result.get("structured_data", {}),
            sources=all_sources,
            confidence=max_sim,
            suggested_followups=result.get("suggested_followups", []),
            navigation=navigation if navigation else None
        )

    def process(self, query: str) -> Dict[str, Any]:
        """
        전체 파이프라인 실행

        Returns:
            {
                "analysis": QueryAnalysis,
                "search_results": [SearchResult],
                "response": StructuredResponse
            }
        """
        # 1. 분석
        analysis = self.analyze_query(query)

        # 2. 검색
        search_results = self.execute_search(analysis)

        # 3. 에이전트 필터링 (관련성 판단)
        filtered_results = self.filter_relevant_results(analysis.original_query, search_results)

        # 4. 응답 생성
        response = self.generate_response(analysis, filtered_results)

        return {
            "analysis": asdict(analysis),
            "search_results": [asdict(sr) for sr in filtered_results],
            "response": asdict(response)
        }
