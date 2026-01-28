# CHALDEAS 마스터 플랜

> 최종 수정: 2026-01-28

## 현재 버전: v0.7.0

### 완료된 주요 기능
- ✅ 3D Globe + Timeline (BCE 3000 ~ 현재)
- ✅ 다언어 지원 (ko/ja/en) + Wikipedia 출처 추적
- ✅ 설정 페이지 (언어, 표시 옵션, API 키)
- ✅ PWA, SEO, 접근성, Analytics, Sentry
- ✅ 법적 문서 (이용약관, 개인정보처리방침)

---

## 관련 문서

| 문서 | 설명 | 상태 |
|------|------|------|
| **이번 대개선 (Event Hierarchy)** |||
| [event_hierarchy/INDEX.md](event_hierarchy/INDEX.md) | 이벤트 계층화 인덱스 | 🔥 진행중 |
| **파이프라인** |||
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | 책 추가 파이프라인 (LLM 기반) | ✅ 운영 |
| [SOURCE_BOOK_MANAGEMENT.md](SOURCE_BOOK_MANAGEMENT.md) | 소스/책 관리 | ✅ 운영 |
| [BOOK_CONTEXT_TRACKING_PLAN.md](BOOK_CONTEXT_TRACKING_PLAN.md) | 책 Context 역추적 | 📋 계획 |
| [BOOK_INTEGRATION_STATUS.md](BOOK_INTEGRATION_STATUS.md) | 책 통합 현황 | ✅ 운영 |
| **미래 계획** |||
| [future_plan/INDEX.md](future_plan/INDEX.md) | V3, 큐레이션, FGO 등 미래 계획 | 📋 계획 |
| **참고** |||
| [JOAN_OF_ARC_SHOWCASE.md](JOAN_OF_ARC_SHOWCASE.md) | 잔다르크 쇼케이스 예제 | 📝 참고 |
| [GPU_THERMAL_MANAGEMENT.md](GPU_THERMAL_MANAGEMENT.md) | GPU 온도 관리 | 📝 참고 |

---

## 현재 상황 (2026-01-27 업데이트)

### DB 상태 (정리 후)
- persons: **275,343개** (이전: 286,566개, -11,223개)
- QID 있는 것: **91,596개** (33%)
- QID 없는 것: 183,747개 (67%)
- 중복 QID: **0개** (해결됨)
- 한글명 있는 것: **1,000개** (Wikidata 보강 시작)
- locations: 40,613개
- events: 46,704개

### 완료된 정리 작업
- ✅ QID 중복 합치기 (10,329개 합침)
- ✅ 쓰레기 데이터 삭제 (894개)
- ✅ Wikidata 정보 보강 시작 (1,000개)
- ⏳ 책 context 역추적 (167권 대기)

### 왜 이렇게 됐나
- 110개 스크립트로 이름 기반 매칭 반복
- Wikidata QID를 Primary Key로 안 씀
- 검증 없이 DB에 삽입
- 상세: `LEGACY_SYSTEM_ANALYSIS.md`

---

## 우리가 가진 원본 자료

| 자료 | 설명 | 상태 |
|------|------|------|
| **Wikidata API** | 1억+ 엔티티, QID로 식별 | 사용 가능 |
| **Gutenberg ZIM** | 80,000권 책 (206GB) | `data/kiwix/gutenberg_en_all.zim` |
| **Wikipedia ZIM** | 영어 위키피디아 | 필요시 다운로드 |
| **FGO 서번트** | 게임 내 역사 인물 | `data/raw/atlas_academy/` |
| **현재 DB** | 286K persons | 쓰레기, QID 있는 것만 salvage 가능 |

---

## 최종 목표

### 뭘 만드는가
**역사 지식 시스템**:
1. 모든 엔티티가 **Wikidata QID로 유일하게 식별**됨
2. 모든 정보에 **출처(어떤 책, 몇 페이지)**가 있음
3. **중복 없음** (한 인물 = 한 레코드)

### 핵심 쿼리 예시
```sql
-- "나폴레옹이 언급된 책들"
SELECT s.title, tm.mention_text
FROM text_mentions tm
JOIN persons p ON tm.entity_id = p.id
JOIN sources s ON tm.source_id = s.id
WHERE p.wikidata_id = 'Q517';

-- "1800년대 프랑스 관련 인물들"
SELECT p.name, p.birth_year, p.death_year
FROM persons p
JOIN person_locations pl ON p.id = pl.person_id
JOIN locations l ON pl.location_id = l.id
WHERE l.wikidata_id = 'Q142'  -- France
AND p.birth_year BETWEEN 1800 AND 1899;
```

---

## 최종 DB 구조

### persons
```sql
CREATE TABLE persons (
    id SERIAL PRIMARY KEY,
    wikidata_id VARCHAR(20) UNIQUE NOT NULL,  -- Q517
    name VARCHAR(500) NOT NULL,                -- canonical name
    name_ko VARCHAR(500),                      -- 한국어 이름
    birth_year INTEGER,
    death_year INTEGER,
    description TEXT,
    wikipedia_url TEXT,
    image_url TEXT,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### entity_aliases
```sql
CREATE TABLE entity_aliases (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- 'person', 'location', 'event'
    entity_id INTEGER NOT NULL,
    alias VARCHAR(500) NOT NULL,
    language VARCHAR(10),              -- 'en', 'ko', 'la'
    alias_type VARCHAR(50),            -- 'canonical', 'alternate', 'translation'
    source VARCHAR(100),               -- 'wikidata', 'book_extraction', 'manual'
    UNIQUE(entity_type, entity_id, alias)
);
```

### text_mentions (출처 추적)
```sql
CREATE TABLE text_mentions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    source_id INTEGER REFERENCES sources(id),
    mention_text VARCHAR(500),         -- "Napoleon led his army"
    context_text TEXT,                 -- 주변 문장
    position_start INTEGER,
    position_end INTEGER,
    chunk_index INTEGER,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### sources (책/문서)
```sql
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(50),           -- 'gutenberg', 'wikipedia', 'manual'
    external_id VARCHAR(100),          -- gutenberg_id, zim_path
    url TEXT,
    author VARCHAR(500),
    year INTEGER,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 새로운 데이터 플로우

```
┌─────────────────────────────────────────────────────────────┐
│                        PHASE 1                              │
│                   깨끗한 Base DB 구축                        │
├─────────────────────────────────────────────────────────────┤
│  1. 현재 DB에서 QID 있는 것만 추출                           │
│  2. QID 기준 중복 제거                                       │
│  3. Wikidata에서 기본 정보 보강                              │
│                                                              │
│  결과: ~90,000 persons (QID 확인된 것만)                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        PHASE 2                              │
│                  책에서 엔티티 추출                          │
├─────────────────────────────────────────────────────────────┤
│  개선된 프롬프트:                                            │
│  - full name + epithet 추출                                  │
│  - context 포함                                              │
│                                                              │
│  출력 예시:                                                   │
│  {                                                           │
│    "name": "Richard the Lionheart",                          │
│    "context": "King of England, led Third Crusade",          │
│    "time_hint": "12th century"                               │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        PHASE 3                              │
│                   Wikidata 매칭                              │
├─────────────────────────────────────────────────────────────┤
│  각 추출된 엔티티에 대해:                                     │
│                                                              │
│  1. Wikidata API 검색 (name + context)                       │
│  2. 후보 중 best match 선택 (description 비교)               │
│  3. QID 확정 → Q190112 (Richard I of England)               │
│                                                              │
│  QID 없으면 → "미확인" 큐로                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        PHASE 4                              │
│                     DB 연결/생성                             │
├─────────────────────────────────────────────────────────────┤
│  QID로 DB 조회:                                              │
│                                                              │
│  있음 → text_mention 추가 (출처 기록)                        │
│  없음 → Wikidata에서 정보 가져와 새 레코드 생성              │
│                                                              │
│  alias도 저장 ("Richard the Lionheart" → Q190112)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 실행 계획

### Step 1: DB 정리 (1일)
```python
# 현재 DB에서 QID 있고 unique한 것만 추출
# 새 테이블로 migration
```

### Step 2: Wikidata 검색 함수 (1일)
```python
def search_wikidata(name: str, context: str) -> Optional[str]:
    """
    Wikidata API로 검색, QID 반환
    context를 활용해 disambiguation
    """
```

### Step 3: 추출 프롬프트 개선 (1일)
```python
prompt = """
Extract with FULL identification:
- Complete names with titles: "Richard I of England"
- Context: "King who led Third Crusade"
"""
```

### Step 4: 매칭 파이프라인 재구현 (2일)
```python
def match_entity(extracted: dict) -> MatchResult:
    # 1. Wikidata 검색
    # 2. QID로 DB 조회
    # 3. 연결 또는 생성
```

### Step 5: 기존 166권 재처리 (ongoing)
- 새 프롬프트로 재추출 또는
- 기존 데이터 + Wikidata 검색

---

## 문서 구조

```
docs/planning/
├── MASTER_PLAN.md               ← 이 문서 (최상위)
│
├── event_hierarchy/             ← 🔥 이번 대개선
│   ├── INDEX.md                 ← 인덱스
│   ├── 00_OVERVIEW.md           ← 마스터 플랜
│   ├── 01_SCHEMA.md             ← DB 스키마
│   ├── 02_WARS.md ~ 06_RELIGION.md  ← 카테고리별 이벤트
│   ├── 07_EVENT_RELATIONS.md    ← 이벤트 간 관계
│   ├── 08_VECTOR_MODEL.md       ← 벡터 기반 역사 모델
│   └── 09_RELATION_PIPELINE.md  ← 관계 후처리 파이프라인
│
├── curation/                    ← ⏸️ 보류 (대규모 작업)
│   ├── CURATION_AND_FGO_MASTER_PLAN.md
│   ├── CURATION_SYSTEM.md
│   └── OPEN_CURATION_VISION.md
│
├── [파이프라인]
│   ├── PIPELINE_GUIDE.md
│   ├── SOURCE_BOOK_MANAGEMENT.md
│   ├── BOOK_CONTEXT_TRACKING_PLAN.md
│   └── BOOK_INTEGRATION_STATUS.md
│
├── [참고]
│   ├── JOAN_OF_ARC_SHOWCASE.md
│   └── GPU_THERMAL_MANAGEMENT.md
│
├── deprecated/                   ← 완료/대체된 문서 (40+)
└── completed/                    ← 완료된 Phase 보고서
```

---

## 현재 시스템 아키텍처 (2026-01-27)

### API 구조

```
/api/v1/
├── events/           # 이벤트 CRUD
├── locations/        # 장소 CRUD
├── persons/          # 인물 CRUD
│   └── /{id}/sources # 인물이 언급된 책들 ✨NEW
├── sources/          # 책/문서 관리 ✨NEW
│   ├── /             # 소스 목록 (75,151개)
│   ├── /{id}         # 소스 상세
│   ├── /{id}/persons # 소스에 언급된 인물들
│   └── /{id}/mentions # 멘션 컨텍스트
├── story/            # 스토리 API ✨NEW
│   └── /person/{id}  # 인물 스토리 → 지도 노드
├── search/           # 통합 검색
├── chat/             # AI 챗
└── showcases/        # 쇼케이스 (잔다르크 등)
```

### LLM 파이프라인

```
책(Source) ──→ LLM 엔티티 추출 ──→ Wikidata 매칭 ──→ DB 저장
                   │                      │
                   ▼                      ▼
            gpt-5-nano             QID로 중복 방지
            (기본 모델)
```

**사용 모델:**
| 모델 | 용도 | 비용 |
|-----|------|------|
| gpt-5-nano | 엔티티 추출 (기본) | $0.10/1M tokens |
| gpt-5-mini | 복잡한 매칭 | $0.30/1M tokens |
| gpt-5.1-chat-latest | 고품질 추출 (폴백) | $2.50/1M tokens |

### 파이프라인 스크립트 위치

```
poc/scripts/
├── test_source_ingestion_openai.py  # 소스 인제스천 테스트
├── import_sources_and_mentions.py   # DB 임포트
├── wikidata_match_*.py              # Wikidata 매칭
└── ...

tools/book_extractor/                 # 웹 UI (개발중)
├── server.py
└── entity_matcher.py
```

---

## 핵심 원칙

1. **Wikidata QID = Primary Key**
   - QID 없으면 DB에 안 넣음
   - 이름은 alias일 뿐

2. **Wikidata First**
   - 추출 → Wikidata 검색 → QID 확정 → DB
   - 우리가 disambiguation 안 함, Wikidata가 해줌

3. **출처 추적**
   - 모든 정보는 어디서 왔는지 기록
   - text_mentions로 책 연결

4. **점진적 구축**
   - 확실한 것만 DB에
   - 불확실한 것은 "미확인" 큐

5. **LLM 기반 추출**
   - NER 대신 LLM 사용 (gpt-5-nano)
   - 컨텍스트 포함 추출로 정확도 향상
