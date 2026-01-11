# CHALDEAS Data Pipeline V2 Plan

**Date**: 2026-01-08
**Status**: Draft
**Author**: Claude + User

---

## 1. Background

### Current Pipeline (V1) - Problems Identified

```
Source Documents (76,023)
    ↓ NER Extraction (GPT-5-nano, ~$47)
Raw Entities (events, persons, locations)
    ↓ Simple String Matching (BROKEN)
Events with wrong locations assigned
    ↓ Enrichment Pass (GPT-5.1, ~$115)
Fixed Events
```

**Issues:**
- Context lost during NER extraction
- Location matching by string caused major errors (e.g., Battle of Thermopylae → Vasio, France)
- Two-pass approach: cheap extraction + expensive fix = inefficient
- Total cost: ~$162 for questionable quality

---

## 2. Proposed Architecture

### Two-Track Approach

| Track | Data | Method | Status |
|-------|------|--------|--------|
| **Track A** | Existing 10,428 events | Enrichment only (metadata fix) | In Progress |
| **Track B** | New incoming documents | Integrated extraction + enrichment | To Build |

---

## 3. Track A: Existing Data Enrichment

### Scope
- Fix metadata for 10,428 existing event records
- NO summary generation (requires multi-source aggregation)

### Output Fields
```json
{
  "id": 57,
  "record_type": "event | article | concept | period",
  "title_clean": "Battle of Chaeronea",
  "year_start": -338,
  "year_end": -338,
  "year_precision": "exact | year | decade | century",
  "era": "CLASSICAL",
  "location_name": "Chaeronea",
  "location_modern": "Chaeronea, Greece",
  "latitude": 38.482,
  "longitude": 22.821,
  "location_type": "battlefield | city | region | country",
  "location_confidence": "high | medium | low",
  "category": "battle | war | treaty | culture | ...",
  "civilization": "Greek",
  "confidence": "high | medium | low",
  "needs_review": false
}
```

### Cost & Timeline
- Model: gpt-5.1-chat-latest
- Events: 10,428
- Est. Cost: ~$80-85 (without summaries)
- Script: `poc/scripts/enrich_events_llm.py`

---

## 4. Track B: Integrated Document Processing (New)

### Concept
Process new source documents with extraction + enrichment in a single pass.

```
New Source Document
    ↓ Single LLM Call (GPT-5.1 or similar)
    - Read full document context
    - Identify historical events/entities
    - Extract with full metadata
    - Geocode with context
    ↓
Enriched Event Records (ready for DB)
```

### Advantages (왜 통합 추출인가?)

1. **Full Context**: LLM이 문서 전체를 보고 추출
   - "마라톤에서 밀티아데스가..." → 인물-이벤트-장소 관계 자동 파악
   - 문맥 없이 "Marathon" 만 보면 그리스인지 미국 보스턴인지 모름

2. **Accurate Geocoding**: 주변 문맥으로 위치 정확도 향상
   - "페르시아 전쟁 중 마라톤 전투" → 그리스 마라톤 확정
   - 단순 string matching으로 Vasio, France 매칭되는 오류 방지

3. **Relationship Extraction**: 관계를 같이 추출
   - 누가 어디서 무엇을 했는지 한번에
   - 나중에 매칭하려면 컨텍스트 손실

4. **No Orphaned Entities**: 연결 안 된 고아 데이터 없음
   - 인물은 있는데 어떤 이벤트 참여했는지 모르는 상황 방지

5. **Single Pass = Cost Efficient**
   - 추출 → 수정 → 연결 3단계보다 1단계가 저렴

### Output per Document (통합 추출 스키마)

문서 하나에서 이벤트, 인물, 장소, 그리고 관계를 모두 추출:

```json
{
  "source_id": "new_doc_001",
  "source_title": "Decisive Events in History",
  "source_author": "John Smith",
  "source_year": 2020,

  "events_extracted": [
    {
      "temp_id": "evt_001",
      "title_clean": "Battle of Marathon",
      "year_start": -490,
      "year_end": -490,
      "year_precision": "exact",
      "era": "CLASSICAL",
      "location_ref": "loc_001",
      "category": "battle",
      "civilization": "Greek",
      "participant_refs": ["per_001", "per_002"],
      "mention_context": "The Battle of Marathon in 490 BCE was...",
      "page_numbers": [23, 24, 25]
    }
  ],

  "persons_extracted": [
    {
      "temp_id": "per_001",
      "name_clean": "Miltiades",
      "birth_year": -550,
      "death_year": -489,
      "birth_place_ref": "loc_002",
      "nationality": "Greek",
      "occupation": ["general", "politician"],
      "era": "CLASSICAL",
      "related_events": ["evt_001"],
      "mention_context": "Miltiades, the Athenian general who..."
    },
    {
      "temp_id": "per_002",
      "name_clean": "Darius I",
      "birth_year": -550,
      "death_year": -486,
      "nationality": "Persian",
      "occupation": ["king"],
      "era": "CLASSICAL",
      "related_events": ["evt_001"],
      "mention_context": "Persian King Darius I sent his forces..."
    }
  ],

  "locations_extracted": [
    {
      "temp_id": "loc_001",
      "name_historical": "Marathon",
      "name_modern": "Marathon, Greece",
      "latitude": 38.15,
      "longitude": 23.96,
      "location_type": "battlefield",
      "region": "Attica",
      "country_modern": "Greece",
      "related_events": ["evt_001"]
    },
    {
      "temp_id": "loc_002",
      "name_historical": "Athens",
      "name_modern": "Athens, Greece",
      "latitude": 37.98,
      "longitude": 23.73,
      "location_type": "city",
      "region": "Attica",
      "country_modern": "Greece"
    }
  ],

  "relationships": [
    {
      "type": "participated_in",
      "subject": "per_001",
      "object": "evt_001",
      "role": "commander"
    },
    {
      "type": "participated_in",
      "subject": "per_002",
      "object": "evt_001",
      "role": "instigator"
    },
    {
      "type": "occurred_at",
      "subject": "evt_001",
      "object": "loc_001"
    },
    {
      "type": "born_in",
      "subject": "per_001",
      "object": "loc_002"
    }
  ]
}
```

### Relationship Types (추출 가능한 관계)

| Type | Subject | Object | Example |
|------|---------|--------|---------|
| `participated_in` | Person | Event | 밀티아데스 → 마라톤 전투 (commander) |
| `occurred_at` | Event | Location | 마라톤 전투 → 마라톤, 그리스 |
| `born_in` | Person | Location | 알렉산더 → 펠라 |
| `died_in` | Person | Location | 알렉산더 → 바빌론 |
| `ruled` | Person | Location | 다리우스 1세 → 페르시아 제국 |
| `preceded_by` | Event | Event | 살라미스 해전 → 마라톤 전투 (인과) |
| `contemporary_of` | Person | Person | 소크라테스 ↔ 플라톤 |
| `teacher_of` | Person | Person | 소크라테스 → 플라톤 |
| `founded` | Person | Location | 알렉산더 → 알렉산드리아 |

### Cost Estimate (per document)

| Document Size | Tokens (Input) | Output | Est. Cost |
|--------------|----------------|--------|-----------|
| Short (5 pages) | ~2,000 | ~1,000 | ~$0.02 |
| Medium (50 pages) | ~20,000 | ~5,000 | ~$0.08 |
| Long (200 pages) | ~80,000 | ~15,000 | ~$0.28 |
| Very Long (500 pages) | ~200,000 | ~30,000 | ~$0.64 |

**Note**: 출력이 커질수록 더 많은 엔티티/관계 추출. 책 한 권에서 수백 개 엔티티 가능.

### Long Document Handling (긴 문서 처리)

#### 문제
- GPT-5.1 context window: 128K tokens
- 500페이지 책 = ~200K tokens → context 초과
- 잘라서 처리해야 함

#### 청킹 전략

```
┌─────────────────────────────────────────────────────────┐
│                   긴 문서 (500 pages)                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
       ┌─────────┐  ┌─────────┐  ┌─────────┐
       │ Chunk 1 │  │ Chunk 2 │  │ Chunk 3 │
       │ Ch.1-5  │  │ Ch.6-10 │  │ Ch.11-15│
       │ p.1-150 │  │ p.151-300│ │ p.301-500│
       └─────────┘  └─────────┘  └─────────┘
            │             │             │
            ▼             ▼             ▼
       ┌─────────┐  ┌─────────┐  ┌─────────┐
       │Extract 1│  │Extract 2│  │Extract 3│
       │밀티아데스│  │테미스토클│  │밀티아데스│
       │마라톤전투│  │살라미스 │  │재판     │
       └─────────┘  └─────────┘  └─────────┘
```

#### 두 가지 접근법

| 접근법 | 설명 | 장점 | 단점 |
|-------|------|------|------|
| **A. 청크별 분리 유지** | 각 청크 결과를 독립적으로 저장 | 인용 위치 정확 (p.23 vs p.301) | 동일 인물 중복 |
| **B. 추출 후 병합** | 청크 결과를 하나로 합침 | 엔티티 통합 | 인용 위치 모호 |

#### 권장: 하이브리드 방식

```json
{
  "source_id": "book_001",
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "page_range": [1, 150],
      "chapter_range": [1, 5],
      "persons_mentioned": ["per_001", "per_002"],
      "events_mentioned": ["evt_001"]
    },
    {
      "chunk_id": "chunk_2",
      "page_range": [151, 300],
      "chapter_range": [6, 10],
      "persons_mentioned": ["per_003", "per_001"],  // per_001 재등장
      "events_mentioned": ["evt_002"]
    }
  ],

  "entities_unified": {
    "persons": [
      {
        "id": "per_001",
        "name": "Miltiades",
        "mentioned_in_chunks": ["chunk_1", "chunk_2"],
        "page_citations": [23, 45, 301, 315]
      }
    ]
  }
}
```

**핵심**:
- 엔티티는 책 전체에서 통합 (밀티아데스 = 하나)
- 인용 정보는 청크별로 보존 (p.23에서 언급, p.301에서 재언급)
- 나중에 "밀티아데스가 이 책 어디서 나와?" → [p.23, p.45, p.301, p.315]

---

## 5. Entity Resolution (Deduplication)

### Problem
새 문서에서 추출한 이벤트가 기존 이벤트와 같은 건지 판단 필요:

| 새로 추출 | 기존 DB | 같은 이벤트? |
|----------|---------|-------------|
| "Battle of Marathon" | "Battle of Marathon" | ✅ 확실히 동일 |
| "Marathon, Battle of" | "Battle of Marathon" | ✅ 동일 (표기 차이) |
| "First Battle of Marathon" | "Battle of Marathon" | ❓ 검토 필요 |
| "Battle of Thermopylae" | "Battle of Marathon" | ❌ 다른 이벤트 |

### Resolution Workflow

```
새 이벤트 추출
    ↓
┌─────────────────────────────────┐
│  1. 유사 이벤트 검색            │
│     - 제목 유사도 (fuzzy match) │
│     - 연도 범위 (±10년)         │
│     - 위치 거리 (±100km)        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  2. 후보 목록 생성              │
│     - 유사도 점수 계산          │
│     - Top 5 후보 반환           │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  3. 판정                        │
│     - AUTO MERGE: 유사도 > 95%  │
│     - AUTO NEW: 유사도 < 50%    │
│     - REVIEW: 50-95% (수동검토) │
└─────────────────────────────────┘
    ↓
┌───────────┬───────────┬─────────────┐
│ MERGE     │ NEW       │ REVIEW      │
│ 기존에 연결│ 새로 생성 │ 큐에 추가   │
└───────────┴───────────┴─────────────┘
```

### Similarity Scoring

```python
def calculate_similarity(new_event, existing_event):
    scores = {
        'title': fuzzy_match(new.title, existing.title),      # 0-100
        'year': year_proximity(new.year, existing.year),       # 0-100
        'location': geo_distance(new.coords, existing.coords), # 0-100
        'category': 100 if new.category == existing.category else 50
    }

    # Weighted average
    weights = {'title': 0.4, 'year': 0.3, 'location': 0.2, 'category': 0.1}
    return sum(scores[k] * weights[k] for k in scores)
```

### Data Model for Resolution

```sql
-- 검토 대기 큐
CREATE TABLE entity_resolution_queue (
    id SERIAL PRIMARY KEY,
    new_event_data JSONB,           -- 새로 추출된 이벤트
    source_id INT,                   -- 출처 문서
    candidate_event_ids INT[],       -- 유사 후보 ID 목록
    similarity_scores FLOAT[],       -- 각 후보별 유사도
    status VARCHAR(20),              -- pending / merged / new_created / rejected
    resolved_by VARCHAR(50),         -- auto / user_id
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 병합 이력
CREATE TABLE entity_merge_history (
    id SERIAL PRIMARY KEY,
    target_event_id INT,             -- 병합 대상 (살아남는 이벤트)
    merged_event_id INT,             -- 병합된 이벤트 (또는 새 추출 데이터)
    merge_reason TEXT,
    merged_at TIMESTAMP DEFAULT NOW()
);
```

### UI for Manual Review

검토가 필요한 케이스를 위한 UI:

```
┌─────────────────────────────────────────────────────────────┐
│ Entity Resolution Review                                     │
├─────────────────────────────────────────────────────────────┤
│ NEW EXTRACTION:                                              │
│   Title: "The Marathon Battle"                               │
│   Year: -490                                                 │
│   Location: Marathon, Greece (38.15, 23.96)                  │
│   Source: "Decisive Events in History" (p.23)                │
│                                                              │
│ SIMILAR EXISTING EVENTS:                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ○ [92%] Battle of Marathon (-490, Marathon, Greece)     │ │
│ │   → 45 sources already linked                           │ │
│ │                                                         │ │
│ │ ○ [67%] Battle of Marathon (1934) (Greece)              │ │
│ │   → Different event (modern commemoration)              │ │
│ │                                                         │ │
│ │ ○ [Create as New Event]                                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ [Merge with Selected]  [Create New]  [Skip]                  │
└─────────────────────────────────────────────────────────────┘
```

### Batch Processing Option

대량 처리 시:
1. 자동 판정 (>95% 또는 <50%) 먼저 처리
2. 검토 필요 건만 큐에 보관
3. 나중에 일괄 검토 또는 개별 검토

---

## 6. Implementation Plan

### Phase 1: Complete Track A (Existing Data)
- Current priority
- [ ] Remove summary from enrichment prompt
- [ ] Run full enrichment on 10,428 events (~$80)
- [ ] Apply results to database
- [ ] Validate sample of results

### Phase 2: Build Track B Pipeline
- [ ] Design integrated extraction prompt
- [ ] Handle context window limits (chunking for long docs)
- [ ] Implement deduplication logic
- [ ] Build source ingestion API
- [ ] Test on 10-50 new documents

### Phase 3: Curation Layer (Future)
- [ ] Multi-source aggregation for summaries
- [ ] Historical Chain generation
- [ ] This is SEPARATE from extraction/enrichment

---

## 6. Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │         SOURCE DOCUMENTS            │
                    └─────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │   EXISTING DATA   │           │    NEW DOCS       │
        │   (10,428 events) │           │   (incoming)      │
        └───────────────────┘           └───────────────────┘
                    │                               │
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │   Track A:        │           │   Track B:        │
        │   Event Metadata  │           │   통합 추출       │
        │   Enrichment      │           │   Events+Persons  │
        │   (gpt-5.1-chat)  │           │   +Locations+Rels │
        └───────────────────┘           └───────────────────┘
                    │                               │
                    │                               ▼
                    │                   ┌───────────────────┐
                    │                   │ Entity Resolution │
                    │                   │ (Deduplication)   │
                    │                   └───────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                    ┌─────────────────────────────────────┐
                    │         KNOWLEDGE BASE              │
                    ├─────────────────────────────────────┤
                    │   Events     │ 10,428+ records      │
                    │   Persons    │ enriched metadata    │
                    │   Locations  │ accurate coords      │
                    │   Relations  │ person↔event↔place   │
                    │   Sources    │ 76,023 documents     │
                    └─────────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────┐
                    │         CURATION LAYER              │
                    │   (Multi-source aggregation)        │
                    ├─────────────────────────────────────┤
                    │   - Historical Chains (인과관계)    │
                    │   - Person Stories (생애)           │
                    │   - Place Stories (장소 역사)       │
                    │   - Era Stories (시대 종합)         │
                    │   - Synthesized Summaries           │
                    └─────────────────────────────────────┘
```

---

## 7. File Locations

| Component | Path |
|-----------|------|
| Track A Script | `poc/scripts/enrich_events_llm.py` |
| Track B Script | `poc/scripts/extract_from_source.py` (TBD) |
| Results | `poc/data/enrichment_results/` |
| This Doc | `docs/planning/DATA_PIPELINE_V2.md` |

---

## 8. Open Questions

1. **Batch API**: Track B could use Batch API (gpt-5 supports it) for 50% cost reduction
2. ~~**Chunking**: How to handle documents > 128K tokens?~~ → 해결: 하이브리드 방식 (청크별 추출 + 엔티티 통합)
3. **Deduplication threshold**: How similar must events be to merge? (현재: >95% auto-merge, <50% auto-new)
4. **Priority**: Which new documents to process first?
5. **Chunk 내 동일 엔티티 인식**: 같은 청크 내에서 "Miltiades" = "밀티아데스" = "the Athenian general" 인식 방법

---

## 9. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-08 | Two-track approach | Fix existing data cheaply, do new data right |
| 2026-01-08 | No summaries in enrichment | Summaries need multi-source aggregation (curation) |
| 2026-01-08 | gpt-5.1-chat-latest for Track A | 100% success rate, cheaper than alternatives |
| 2026-01-08 | Track B: 통합 추출 (Events+Persons+Locations+Relations) | 문맥 보존, 관계 자동 추출, 고아 엔티티 방지 |
