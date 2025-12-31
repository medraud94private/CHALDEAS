"""
LLM Assistant - GPT-4o-mini 기반 데이터 처리 보조 함수

역할:
- 계층 구조 제안
- 관계 추출
- 엔티티 매칭 검증
"""

import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from openai import OpenAI
import time


@dataclass
class HierarchySuggestion:
    """LLM이 제안한 계층 구조"""
    event_id: str
    parent_id: Optional[str]
    level: int  # 0=최상위, 1=전쟁, 2=캠페인, 3=전투
    event_type: str  # war_series, war, campaign, battle, siege, treaty
    reasoning: str


@dataclass
class NewParentEvent:
    """LLM이 제안한 새 상위 이벤트"""
    title: str
    title_ko: Optional[str]
    date_start: int
    date_end: Optional[int]
    event_type: str
    description: str


@dataclass
class RelationSuggestion:
    """LLM이 제안한 관계"""
    from_id: str
    to_id: str
    relation_type: str
    strength: int  # 1-5
    reasoning: str


class LLMAssistant:
    """LLM 기반 데이터 처리 도우미"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.request_count = 0
        self.total_tokens = 0

    def _call_llm(self, prompt: str, system_prompt: str = None, temperature: float = 0.3) -> Dict:
        """LLM 호출 (JSON 응답)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            self.request_count += 1
            self.total_tokens += response.usage.total_tokens

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[LLM Error] {e}")
            return {"error": str(e)}

    def suggest_hierarchy(self, events: List[Dict]) -> Dict[str, Any]:
        """
        이벤트 목록의 계층 구조 제안

        Args:
            events: 이벤트 목록 (id, title, date_start, date_end, description, category)

        Returns:
            {
                "hierarchy": [HierarchySuggestion],
                "new_parents": [NewParentEvent],
                "reasoning": str
            }
        """
        system_prompt = """당신은 역사 전문가입니다. 역사 이벤트들의 계층 구조를 분석합니다.

규칙:
1. 전투(battle)는 캠페인(campaign)이나 전쟁(war)에 속함
2. 캠페인은 전쟁에 속함
3. 전쟁은 전쟁 시리즈(war_series)에 속할 수 있음
4. 조약(treaty)은 보통 전쟁의 종결점
5. 시간적으로 포함되어야 함 (자식 이벤트가 부모 기간 내)

레벨 정의:
- 0: 최상위 (예: 십자군 전쟁 전체)
- 1: 전쟁 (예: 1차 십자군)
- 2: 캠페인/원정 (예: 레반트 원정)
- 3: 개별 전투/공성전 (예: 안티오키아 공성전)

JSON 형식으로 응답하세요."""

        # 이벤트 정보 포맷팅
        events_text = "\n".join([
            f"- [{e.get('id')}] {e.get('title')} ({e.get('date_start')}-{e.get('date_end', '?')}) - {e.get('category', 'unknown')}"
            for e in events[:50]  # 최대 50개
        ])

        prompt = f"""다음 역사 이벤트들의 계층 구조를 분석하세요.

## 이벤트 목록
{events_text}

## 작업
1. 각 이벤트가 속하는 상위 이벤트를 식별하세요
2. 상위 이벤트가 목록에 없으면 새로 제안하세요
3. 각 이벤트의 레벨과 타입을 지정하세요

## 출력 형식 (JSON)
{{
  "hierarchy": [
    {{"event_id": "id", "parent_id": "상위id 또는 null", "level": 3, "event_type": "battle", "reasoning": "이유"}}
  ],
  "new_parents": [
    {{"title": "제목", "title_ko": "한국어", "date_start": -490, "date_end": -479, "event_type": "war", "description": "설명"}}
  ],
  "overall_reasoning": "전체 분석 근거"
}}"""

        result = self._call_llm(prompt, system_prompt)

        if "error" in result:
            return {"hierarchy": [], "new_parents": [], "reasoning": result["error"]}

        return {
            "hierarchy": [
                HierarchySuggestion(**h) for h in result.get("hierarchy", [])
            ],
            "new_parents": [
                NewParentEvent(**p) for p in result.get("new_parents", [])
            ],
            "reasoning": result.get("overall_reasoning", "")
        }

    def extract_relations(self, main_event: Dict, context_events: List[Dict]) -> List[RelationSuggestion]:
        """
        이벤트 간 관계 추출

        Args:
            main_event: 주 이벤트
            context_events: 비교할 주변 이벤트들

        Returns:
            관계 제안 목록
        """
        system_prompt = """당신은 역사 관계 분석 전문가입니다.

관계 유형:
- causes: A가 B의 직접적 원인
- follows: A 직후에 B 발생 (인과적 연결)
- part_of: A는 B의 일부
- related_to: 일반적 연관 (같은 전쟁, 같은 인물 등)
- opposes: A와 B는 대립 관계 (적대 세력)

strength (1-5):
- 5: 명확한 직접 관계
- 3: 간접적이지만 확실한 연관
- 1: 약한 연관

JSON 형식으로 응답하세요."""

        context_text = "\n".join([
            f"- [{e.get('id')}] {e.get('title')} ({e.get('date_start')})"
            for e in context_events[:20]
        ])

        prompt = f"""다음 이벤트와 주변 이벤트들의 관계를 분석하세요.

## 주 이벤트
- ID: {main_event.get('id')}
- 제목: {main_event.get('title')}
- 날짜: {main_event.get('date_start')} - {main_event.get('date_end', '?')}
- 설명: {main_event.get('description', '')[:300]}

## 주변 이벤트들
{context_text}

## 출력 형식 (JSON)
{{
  "relations": [
    {{"from_id": "주이벤트id", "to_id": "관련이벤트id", "relation_type": "causes", "strength": 4, "reasoning": "이유"}}
  ]
}}"""

        result = self._call_llm(prompt, system_prompt)

        if "error" in result:
            return []

        return [
            RelationSuggestion(**r) for r in result.get("relations", [])
        ]

    def verify_entity_match(self, entity1: Dict, entity2: Dict) -> Dict[str, Any]:
        """
        두 엔티티가 같은 것을 가리키는지 검증

        Returns:
            {"is_match": bool, "confidence": float, "reasoning": str}
        """
        prompt = f"""다음 두 역사 기록이 같은 사건/인물을 가리키는지 판단하세요.

## 기록 1
- 제목: {entity1.get('title')}
- 날짜: {entity1.get('date_start')}
- 설명: {entity1.get('description', '')[:200]}
- 출처: {entity1.get('source_type')}

## 기록 2
- 제목: {entity2.get('title')}
- 날짜: {entity2.get('date_start')}
- 설명: {entity2.get('description', '')[:200]}
- 출처: {entity2.get('source_type')}

## 출력 형식 (JSON)
{{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "판단 근거"
}}"""

        result = self._call_llm(prompt)

        if "error" in result:
            return {"is_match": False, "confidence": 0, "reasoning": result["error"]}

        return result

    def get_stats(self) -> Dict[str, int]:
        """사용 통계 반환"""
        return {
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.total_tokens * 0.00015 / 1000, 4)  # gpt-4o-mini 기준
        }


# 배치 처리 유틸리티
def group_events_by_era(events: List[Dict], window_years: int = 100) -> List[List[Dict]]:
    """시대별로 이벤트 그룹화 (LLM 컨텍스트 효율화)"""
    sorted_events = sorted(events, key=lambda x: x.get('date_start', 0))

    batches = []
    current_batch = []
    batch_start = None

    for event in sorted_events:
        date = event.get('date_start', 0)

        if batch_start is None:
            batch_start = date
            current_batch = [event]
        elif date - batch_start <= window_years:
            current_batch.append(event)
        else:
            if current_batch:
                batches.append(current_batch)
            current_batch = [event]
            batch_start = date

    if current_batch:
        batches.append(current_batch)

    return batches


def group_events_by_region(events: List[Dict], distance_km: float = 500) -> List[List[Dict]]:
    """지역별로 이벤트 그룹화"""
    from math import radians, sin, cos, sqrt, atan2

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # 지구 반경 km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    # 좌표가 있는 이벤트만 필터링
    events_with_coords = [e for e in events if e.get('latitude') and e.get('longitude')]
    events_without_coords = [e for e in events if not (e.get('latitude') and e.get('longitude'))]

    # 간단한 클러스터링 (greedy)
    batches = []
    used = set()

    for i, event in enumerate(events_with_coords):
        if i in used:
            continue

        cluster = [event]
        used.add(i)

        for j, other in enumerate(events_with_coords):
            if j in used:
                continue

            dist = haversine(
                event['latitude'], event['longitude'],
                other['latitude'], other['longitude']
            )

            if dist <= distance_km:
                cluster.append(other)
                used.add(j)

        batches.append(cluster)

    # 좌표 없는 이벤트는 별도 배치
    if events_without_coords:
        batches.append(events_without_coords)

    return batches


if __name__ == "__main__":
    # 테스트
    assistant = LLMAssistant()

    test_events = [
        {"id": "evt_1", "title": "Battle of Marathon", "date_start": -490, "category": "battle"},
        {"id": "evt_2", "title": "Battle of Thermopylae", "date_start": -480, "category": "battle"},
        {"id": "evt_3", "title": "Battle of Salamis", "date_start": -480, "category": "battle"},
        {"id": "evt_4", "title": "Battle of Plataea", "date_start": -479, "category": "battle"},
    ]

    print("Testing hierarchy suggestion...")
    result = assistant.suggest_hierarchy(test_events)
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))

    print("\nStats:", assistant.get_stats())
