# CHALDEAS 펜딩 변경사항

## 완료된 항목
1. ✅ 타임라인 재생 속도: 10초 → 5초 (`frontend/src/App.tsx` line 85)
2. ✅ EventDetailPanel - LOG ID를 출처로 변경 (`frontend/src/components/detail/EventDetailPanel.tsx`)
3. ✅ History Agent - 20개 가져오기 + 에이전트 필터링 (`backend/app/core/sheba/history_agent.py`)
4. ✅ ChatPanel - SHEBA 검색 후 자동 타임라인 이동 (`frontend/src/components/chat/ChatPanel.tsx`)
5. ✅ GlobeStore/Container - 검색 결과 지도 하이라이트 (`frontend/src/store/globeStore.ts`, `frontend/src/components/globe/GlobeContainer.tsx`)

## 이전 미완료 변경사항 (모두 적용됨)

### 1. EventDetailPanel - LOG ID를 출처로 변경
**파일**: `frontend/src/components/detail/EventDetailPanel.tsx`
**위치**: Line 94-96

변경 전:
```tsx
<div className="detail-meta">
  LOG ID: {event.id}
</div>
```

변경 후:
```tsx
<div className="detail-meta">
  {event.sources && event.sources.length > 0 ? (
    <span className="source-ref" title={event.sources[0].name}>
      📜 {event.sources[0].type === 'primary' ? 'PRIMARY' : 'SECONDARY'}: {event.sources[0].name?.slice(0, 30)}{event.sources[0].name && event.sources[0].name.length > 30 ? '...' : ''}
    </span>
  ) : (
    <span className="source-ref">📚 CHALDEAS ARCHIVE #{event.id}</span>
  )}
</div>
```

---

### 2. History Agent - 20개 가져오기 + 에이전트 필터링
**파일**: `backend/app/core/sheba/history_agent.py`

#### 2.1 import 변경 (Line 14)
```python
from dataclasses import dataclass, asdict, field
```

#### 2.2 StructuredResponse에 navigation 필드 추가 (Line 75-85 부근)
```python
@dataclass
class StructuredResponse:
    intent: str
    format: str
    answer: str
    structured_data: Dict[str, Any]
    sources: List[Dict]
    confidence: float
    suggested_followups: List[str]
    navigation: Optional[Dict[str, Any]] = field(default=None)  # 추가
```

#### 2.3 execute_search - limit 변경 (Line 298-324)
- 비교 검색: `limit=3` → `limit=10`
- 일반 검색: `limit=5` → `limit=20`

#### 2.4 filter_relevant_results 메서드 추가 (execute_search 다음에)
```python
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
```

#### 2.5 generate_response - navigation 추가 (all_sources에 추가 필드)
```python
all_sources.append({
    "id": doc.get("content_id"),
    "title": meta.get("title", ""),
    "similarity": doc.get("similarity", 0),
    "date_start": meta.get("date_start"),      # 추가
    "latitude": meta.get("latitude"),          # 추가
    "longitude": meta.get("longitude"),        # 추가
})
```

그리고 return 전에:
```python
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
    ...,
    navigation=navigation if navigation else None  # 추가
)
```

#### 2.6 process - 필터링 단계 추가
```python
def process(self, query: str) -> Dict[str, Any]:
    analysis = self.analyze_query(query)
    search_results = self.execute_search(analysis)
    filtered_results = self.filter_relevant_results(analysis.original_query, search_results)  # 추가
    response = self.generate_response(analysis, filtered_results)  # search_results → filtered_results
    ...
```

---

### 3. Frontend - SHEBA 검색 후 자동 타임라인 이동
**파일**: `frontend/src/components/chat/ChatPanel.tsx`

response.navigation.target_year가 있으면:
```typescript
import { useTimelineStore } from '../../store/timelineStore'

// onSuccess 내에서:
if (agentResponse.response.navigation?.target_year) {
    useTimelineStore.getState().setCurrentYear(agentResponse.response.navigation.target_year)
}
```

---

### 4. Frontend - 검색 결과 지도 하이라이트
**파일**: `frontend/src/store/globeStore.ts`

```typescript
// 상태 추가
highlightedLocations: Array<{title: string, lat: number, lng: number, year?: number}>,
setHighlightedLocations: (locs) => void,
```

**파일**: `frontend/src/components/globe/GlobeContainer.tsx`

highlightedLocations를 빛나는 마커로 표시, 클릭 시 해당 이벤트로 이동

---

### 5. RESPONSE_PROMPT에 navigation 지시 추가
```
## 출력 (JSON)
navigation에 지도/타임라인 네비게이션 정보 포함:
- target_year: 관련 연도 (BCE는 음수)
- locations: [{"title": "이름", "lat": 위도, "lng": 경도, "year": 연도, "description": "설명"}]
```

---

## 서버 재시작 명령어
```bash
# Backend
cd /c/Projects/Chaldeas/backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload

# Frontend
cd /c/Projects/Chaldeas/frontend && npm run dev -- --port 5200
```

## 포트 (고정)
- Frontend: 5200
- Backend: 8100
- API Docs: http://localhost:8100/docs
