# CHALDEAS Data Pipeline V2 Plan

**Date**: 2026-01-08
**Last Updated**: 2026-01-15
**Status**: In Progress
**Author**: Claude + User

---

## 1. Core Principle: Document-First

> **"소스 문서가 Ground Truth다. Wikidata는 보강 수단일 뿐."**

수만 권의 책을 처리할 시스템. Wikipedia에 없는 인물/사건도 많으므로,
소스 문서 기반 추출이 핵심이고 Wikidata는 선택적 보강 레이어다.

```
┌─────────────────────────────────────────────────────────────────┐
│  PRIMARY: 소스 문서 → LLM 추출 → Entity Resolution → DB        │
├─────────────────────────────────────────────────────────────────┤
│  SECONDARY: Wikidata 매칭 → 메타데이터 보강 (Optional)          │
├─────────────────────────────────────────────────────────────────┤
│  TERTIARY: Wikipedia 링크 → 추가 관계 발견 (Optional)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Overview

```
신규 문서 (수만 권)
     │
     ▼
┌─────────────────────┐
│  LLM 통합 추출      │  ← Primary Source of Truth
│  (Events, Persons,  │
│   Locations, Rels)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Entity Resolution  │  기존 DB와 비교
│  (Deduplication)    │
└──────────┬──────────┘
           │
   ┌───────┼───────┬─────────────┐
   ▼       ▼       ▼             ▼
 일치    신규    애매          노이즈
(>90%)  (유의미) (50-90%)     (<50%)
   │       │       │             │
   ▼       ▼       ▼             ▼
 기존에   DB에   검토 큐        폐기
 소스추가 추가   (보류)

           │
           ▼
┌─────────────────────┐
│  Wikidata 매칭      │  ← Optional Enrichment
│  (검증 & 보강)      │
└──────────┬──────────┘
           │
   ┌───────┴───────┐
   ▼               ▼
 매칭됨         미매칭
   │               │
   ▼               ▼
메타데이터     그대로 유지
보강 + conf↑   (소스 기반)
```

---

## 3. Layer Roles

| Layer | 역할 | 의존성 | 커버리지 |
|-------|------|--------|----------|
| **L1: 소스 문서** | Ground Truth, 엔티티/관계 생성 | 없음 | 100% |
| **L2: Wikidata** | 검증, 메타데이터 보강 | L1 선행 | ~30-40% |
| **L3: Wikipedia** | 추가 관계 발견 | L2 선행 | ~30-40% |

### Wikidata의 가치 (무시하면 안 되는 이유)
1. **검증**: "Socrates 470-399 BCE" → Wikidata 일치 시 confidence ↑
2. **메타데이터**: 이미지, 정확한 좌표, 다국어 이름
3. **관계 확장**: 소스 문서에 없는 연결 발견
4. **정규화**: 소크라테스 = Socrates = Q913 통합

---

## 4. Processing Tracks

### Track A: 기존 데이터 보강 (Enrichment Only)

| 항목 | 값 |
|------|-----|
| 대상 | 기존 10,428 이벤트 |
| 목적 | 메타데이터 수정 (위치, 연도, 카테고리) |
| 방법 | LLM enrichment (gpt-5.1-chat) |
| 비용 | ~$80-85 |

### Track B: 신규 문서 처리 (Full Pipeline)

| 항목 | 값 |
|------|-----|
| 대상 | 신규 입수 문서 (수만 권 예정) |
| 목적 | 통합 추출 + Entity Resolution |
| 방법 | LLM 추출 → 중복 제거 → DB 반영 |
| 핵심 | 문맥 보존, 관계 자동 추출 |

---

## 5. Track B Detail: 신규 문서 통합 추출

### Concept
소스 문서에서 LLM 한 번 호출로 모든 엔티티와 관계를 추출.

```
New Source Document
    ↓ Single LLM Call (GPT-5.1 or similar)
    - Read full document context
    - Identify historical events/entities
    - Extract with full metadata
    - Geocode with context
    ↓
Enriched Records (ready for Entity Resolution)
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

## 6. Entity Resolution (핵심 로직)

> **신규 추출 엔티티를 기존 DB와 비교하여 일치/신규/애매/폐기 분류**

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
│  3. 판정 (4분류)                │
│     - 일치: 유사도 > 90%        │
│     - 신규: 유사도 < 50% + 유의미│
│     - 애매: 50-90% (검토 필요)  │
│     - 노이즈: < 50% + 무의미    │
└─────────────────────────────────┘
    ↓
┌──────────┬──────────┬──────────┬──────────┐
│  일치    │  신규    │  애매    │  노이즈  │
│  (>90%)  │ (유의미) │ (50-90%) │  (<50%)  │
├──────────┼──────────┼──────────┼──────────┤
│ 기존에   │ DB에     │ 검토 큐  │  폐기    │
│ 소스추가 │ 추가     │ (보류)   │          │
└──────────┴──────────┴──────────┴──────────┘

### 유의미 vs 노이즈 판단

| 조건 | 판정 | 예시 |
|------|------|------|
| 역사적 인물/사건 + 구체적 정보 | 유의미 (신규) | "General John Smith (1802-1867)" |
| 일반 명사, 불완전한 정보 | 노이즈 (폐기) | "the king", "a battle" |
| 소설/허구 캐릭터 | 애매 (검토) | "Sherlock Holmes" |
| 출처에 따라 다름 | 애매 (검토) | 신화적 인물 |
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

## 7. Implementation Plan

### 우선순위 원칙

```
1. Document-First: 소스 문서 기반 작업이 최우선
2. Wikidata: 보강 수단, 병렬 진행 가능하나 필수 아님
3. Wikipedia: Wikidata 매칭 후 선택적 확장
```

### Phase 1: Track A - 기존 데이터 보강
- [ ] 기존 10,428 이벤트 메타데이터 보강 (~$80)
- [ ] 빈 설명 채우기 (~25,000개)
- [ ] 결과 DB 적용 및 검증

### Phase 1.5: Wikidata 매칭 (병렬 진행 가능)
- [x] Forward matching 진행 중 (39% → 100%)
- [ ] Reverse matching 결과 DB 적용
- [ ] 매칭된 인물 메타데이터 보강

### Phase 2: Track B - 신규 문서 파이프라인 구축
- [ ] 통합 추출 프롬프트 설계
- [ ] Entity Resolution 로직 구현
- [ ] 검토 큐 UI 구현
- [ ] 10-50개 문서로 테스트

### Phase 3: 대규모 처리
- [ ] 배치 API 활용 (비용 50% 절감)
- [ ] 수천 권 문서 처리
- [ ] 검토 큐 처리 워크플로우

### Phase 4: Wikipedia 링크 확장 (Optional)
- [ ] Wikidata 매칭된 인물 대상
- [ ] Wikipedia 링크 수집
- [ ] 추가 관계 발견

---

**Note**: Description Enrichment은 Track A의 일부로 처리

---

## 9. Database Schema

### Core Entity Tables

```sql
persons:
├── id (PK)
├── name, name_ko, name_original
├── birth_year, death_year        -- 생몰년
├── biography, biography_ko
├── wikidata_id                   -- Optional (있으면 보강)
├── wikipedia_url                 -- Optional
├── role, era, certainty
├── mention_count, avg_confidence -- 데이터 품질 지표
└── embedding                     -- 벡터 검색용

events:
├── id (PK)
├── title, title_ko
├── date_start, date_end          -- BCE는 음수
├── description
├── primary_location_id (FK)
├── category_id (FK)
└── temporal_scale                -- evenementielle/conjuncture/longue_duree

locations:
├── id (PK)
├── name, name_ko
├── latitude, longitude
├── location_type
└── parent_location_id

sources:
├── id (PK)
├── name, title, author
├── type                          -- book/article/document
├── publication_year
└── content                       -- 원문 (청킹용)
```

### Relationship Tables

```sql
event_persons:                    -- 인물 ↔ 이벤트
├── event_id (FK)
├── person_id (FK)
├── role                          -- participant/leader/victim 등
└── description

person_relationships:             -- 인물 ↔ 인물
├── person_id (FK)
├── related_person_id (FK)
├── relationship_type             -- teacher_of/parent_of/rival 등
├── strength, confidence
└── is_bidirectional

event_relationships:              -- 이벤트 ↔ 이벤트 (인과관계)
├── from_event_id (FK)
├── to_event_id (FK)
├── relationship_type             -- caused/preceded/influenced
└── strength, confidence

person_sources:                   -- 출처 추적
├── person_id (FK)
├── source_id (FK)
└── page_reference

event_sources:
├── event_id (FK)
├── source_id (FK)
├── page_reference
└── quote                         -- 인용문
```

### Key Design Principles

1. **wikidata_id는 Optional**: NULL이어도 시스템 정상 동작
2. **Source Attribution**: 모든 엔티티는 출처 추적 가능
3. **Confidence Score**: 데이터 신뢰도 명시적 관리
4. **BCE 날짜**: 음수로 저장 (-490 = 490 BCE)

### Example: Socrates (id=343)

```
persons:
  id: 343
  name: "Socrates"
  birth_year: -470
  death_year: -399
  wikidata_id: "Q913"        ← Wikidata 매칭됨 (optional)
  wikipedia_url: "https://en.wikipedia.org/wiki/Socrates"

event_persons:
  (343, 501, "participant")  → 펠로폰네소스 전쟁
  (343, 502, "defendant")    → 소크라테스 재판

person_relationships:
  (343, 344, "teacher_of")   → 플라톤
  (343, 345, "teacher_of")   → 크세노폰

person_sources:
  (343, 12, "pp.45-67")      → "History of Greek Philosophy"
```

---

## 10. Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │      SOURCE DOCUMENTS (수만 권)      │
                    │         PRIMARY DATA SOURCE          │
                    └─────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │   EXISTING DATA   │           │    NEW DOCS       │
        │   (기존 이벤트)    │           │   (신규 입수)      │
        └───────────────────┘           └───────────────────┘
                    │                               │
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │   Track A:        │           │   Track B:        │
        │   메타데이터 보강  │           │   LLM 통합 추출    │
        └───────────────────┘           └───────────────────┘
                    │                               │
                    │                               ▼
                    │                   ┌───────────────────┐
                    │                   │ Entity Resolution │
                    │                   │ 일치/신규/애매/폐기│
                    │                   └───────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                    ┌─────────────────────────────────────┐
                    │         KNOWLEDGE BASE (DB)         │
                    ├─────────────────────────────────────┤
                    │   Events, Persons, Locations        │
                    │   Relations, Sources                │
                    └─────────────────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
              ┌─────────────────┐    ┌─────────────────┐
              │ Wikidata 매칭   │    │ Curation Layer  │
              │ (Optional)      │    │ Historical Chain│
              │ 검증 & 보강     │    │ Person Story    │
              └────────┬────────┘    └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Wikipedia Links │
              │ (Optional)      │
              │ 추가 관계 발견  │
              └─────────────────┘
```

---

## 10. File Locations

| Component | Path |
|-----------|------|
| Track A Script | `poc/scripts/enrich_events_llm.py` |
| Track B Script | `poc/scripts/extract_from_source.py` (TBD) |
| Entity Resolution | `poc/scripts/entity_resolution.py` (TBD) |
| Wikidata Matching | `poc/scripts/wikidata_reconcile.py` |
| Results | `poc/data/enrichment_results/` |
| This Doc | `docs/planning/DATA_PIPELINE_V2.md` |

---

## 11. Related Documents

| Document | Purpose |
|----------|---------|
| `WIKIDATA_PIPELINE.md` | Wikidata 매칭 상세 |
| `WIKIDATA_ENRICHMENT_ROADMAP.md` | Wikidata/Wikipedia 보강 로드맵 |
| `WIKIPEDIA_LINK_PIPELINE.md` | Wikipedia 링크 수집 (Optional) |

---

## 12. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-08 | Two-track approach | Fix existing data cheaply, do new data right |
| 2026-01-08 | No summaries in enrichment | Summaries need multi-source aggregation (curation) |
| 2026-01-08 | gpt-5.1-chat-latest for Track A | 100% success rate, cheaper than alternatives |
| 2026-01-08 | Track B: 통합 추출 | 문맥 보존, 관계 자동 추출, 고아 엔티티 방지 |
| **2026-01-15** | **Document-First principle** | **Wikidata에 없는 인물도 많음, 소스 문서가 Ground Truth** |
| **2026-01-15** | **4분류 Entity Resolution** | **일치/신규/애매/폐기로 세분화** |
| **2026-01-15** | **Wikidata = Optional Layer** | **보강 수단이지 필수 의존 아님** |

---

## 13. 현재 상황 분석 (2026-01-18)

### 13.1 Wikipedia 추출 데이터 현황

#### poc/data/wikipedia_extract/

| 파일 | 레코드 수 | qid 있음 | 용량 |
|------|----------|----------|------|
| persons.jsonl | 200,427 | 84,680 (42%) | ~100MB |
| events.jsonl | 267,364 | 22,101 (8%) | ~150MB |
| locations.jsonl | 821,848 | 187,588 (23%) | ~500MB |

**레코드 구조:**
```json
{
  "title": "Albert Einstein",
  "qid": "Q937",
  "birth_year": 1879,
  "death_year": 1955,
  "summary": "Albert Einstein \n     \n     \n       \n     \n ...",  // ⚠️ HTML 잔해
  "path": "Albert_Einstein"
}
```

**문제점:**
- `summary`가 전체 본문이 아님 (첫 문단 정도)
- HTML 태그 잔해가 섞여서 텍스트가 깨짐
- **full content가 없음**

#### poc/data/wikipedia_persons/

| 파일 | 레코드 수 | 용량 |
|------|----------|------|
| persons.jsonl | 405,014 | 187MB |

비슷한 구조, 동일한 문제.

### 13.2 DB 현황

| 테이블 | 총 개수 | wikidata_id | wikipedia_url | 본문 |
|--------|---------|-------------|---------------|------|
| persons | 286,609 | 101,839 (35%) | 13,606 (4%) | 57,214 (19%) |
| events | 46,704 | **0 (0%)** | 550 (1%) | 23,225 (49%) |
| locations | 40,613 | **0 (0%)** | **0 (0%)** | 34,299 (84%) |

**Sources 테이블:**
| archive_type | 개수 |
|--------------|------|
| unknown | 76,013 |
| wikipedia | 8,675 |
| gutenberg | 10 |

**Source-Entity 연결:**
| 연결 테이블 | 연결 수 | 연결된 엔티티 |
|------------|--------|--------------|
| person_sources (wikipedia) | 3,134 | 3,113명 |
| event_sources (wikipedia) | 5,466 | 5,454개 |
| location_sources (wikipedia) | **0** | **0개** |

**Sources.content: 모두 NULL** ← 본문 없음

### 13.3 근본 문제

1. **Events에 wikidata_id가 0%** - 출처 추적 불가
2. **Locations에 wikidata_id, wikipedia_url 둘 다 0%**
3. **Sources.content가 NULL** - 본문 저장 안 됨
4. **추출 데이터에 full content 없음** - summary만 있고 그것도 깨짐
5. **연결만 하고 데이터 반영 안 함**
   - Sources 테이블에 연결은 했지만
   - 엔티티 테이블의 wikidata_id/wikipedia_url 업데이트 안 함

### 13.4 전임자가 한 것 vs 안 한 것

**한 것:**
- Wikipedia에서 데이터 추출 (Kiwix ZIM 사용)
- 이름 매칭으로 DB 엔티티와 "연결" 시도
- Sources 테이블에 레코드 생성
- person_sources, event_sources 연결

**안 한 것:**
- ❌ 엔티티 테이블에 wikidata_id 직접 저장
- ❌ 엔티티 테이블에 wikipedia_url 직접 저장
- ❌ Sources.content에 본문 저장
- ❌ 전체 본문 추출 (summary만 추출)
- ❌ locations_sources 연결

---

## 14. 해야 할 것 (올바른 설계)

### 목표

Wikipedia 추출 데이터 **전체** (120만개)를 DB에 임포트.
각 레코드에 다음 정보 **전부** 저장:
- `wikidata_id` ← qid
- `wikipedia_url` ← path로 생성
- `biography/description` ← **전체 본문**

### 현재 추출의 문제

`kiwix_extract_all.py` 282-288줄:
```python
def extract_summary(html: str) -> str:
    text = html_to_text(html[:5000])  # ← 5000자만 봄
    sentences = text.split('.')
    return sentences[0].strip()[:300]  # ← 첫 문장 300자만
```

**5000자 중 첫 문장 300자만 추출**. 전체 본문이 없음.

---

### Phase 1: 전체 본문 재추출

**입력**: Kiwix ZIM 파일 (51GB)
**출력**: 새 JSONL (전체 본문 포함)

```python
# 새 JSONL 구조
{
    "title": "Albert Einstein",
    "qid": "Q937",
    "path": "Albert_Einstein",
    "birth_year": 1879,
    "death_year": 1955,
    "summary": "첫 문단...",           # 기존
    "content": "전체 본문...",          # 신규 - 전체 텍스트
    "wikipedia_url": "https://en.wikipedia.org/wiki/Albert_Einstein"
}
```

**수정 사항**:
1. `html_to_text(html)` 전체 호출 (5000자 제한 제거)
2. `content` 필드에 전체 본문 저장
3. `wikipedia_url` 필드 추가

**예상 결과**:
| 파일 | 레코드 수 | 용량 (예상) |
|------|----------|------------|
| persons.jsonl | ~200,000 | ~2GB |
| events.jsonl | ~267,000 | ~3GB |
| locations.jsonl | ~821,000 | ~8GB |

---

### Phase 2: DB 임포트 (전체)

**입력**: Phase 1 결과 JSONL
**출력**: DB 테이블 (persons, events, locations, sources)

```python
for record in jsonl:
    # 1. 엔티티 테이블에 직접 저장
    entity = Person(
        name=record['title'],
        wikidata_id=record['qid'],
        wikipedia_url=record['wikipedia_url'],
        biography=record['content'],
        birth_year=record['birth_year'],
        death_year=record['death_year'],
    )

    # 2. Sources 테이블에도 저장
    source = Source(
        title=record['title'],
        url=record['wikipedia_url'],
        archive_type='wikipedia',
        content=record['content'],  # 본문도 저장
    )

    # 3. 연결
    entity_source = PersonSource(person=entity, source=source)
```

**중복 체크**: title + birth_year/death_year 또는 qid로 중복 판별

---

### Phase 3: Entity Resolution

기존 DB 데이터 (286,609 persons, 46,704 events, 40,613 locations)와 병합.

```
Wikipedia 데이터 (Phase 1-2)
         │
         ▼
┌─────────────────────┐
│  중복 체크          │
│  - qid 일치?        │
│  - title 유사도?    │
│  - 날짜 범위?       │
└─────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 기존과     신규
 중복       추가
    │
    ▼
  병합
  (기존 데이터 보강)
```

**병합 규칙**:
- qid가 같으면 → 같은 엔티티, 정보 병합
- qid 없고 title 일치 + 날짜 유사 → 같은 엔티티, 정보 병합
- 위 둘 다 아니면 → 새 엔티티로 추가

---

### 실행 순서

| Phase | 작업 | 예상 시간 | 결과 |
|-------|------|----------|------|
| 1 | 전체 본문 재추출 | 수 시간 | 120만개 × 본문 JSONL |
| 2 | DB 임포트 | 수 시간 | 모든 레코드에 qid/url/본문 |
| 3 | Entity Resolution | 수 시간 | 기존 데이터와 병합 완료 |

---

### 스크립트 위치

| Phase | 스크립트 | 상태 |
|-------|----------|------|
| 1 | `poc/scripts/kiwix_extract_full.py` | 작성 필요 |
| 2 | `poc/scripts/import_wikipedia_to_db.py` | 작성 필요 |
| 3 | `poc/scripts/entity_resolution.py` | 작성 필요 |
