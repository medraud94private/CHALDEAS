# NER Pipeline Design - Integrated Entity Extraction System

## Overview

대규모 역사 문서에서 엔티티를 추출하고 저장하는 파이프라인 설계.

**총 문서 수**: 76,026개
- British Library: 63,985 (JSON)
- Gutenberg: 12,031 (TXT)
- Arthurian: 10 (TXT)

---

## Phase 1: NER Extraction (Batch API)

### 목적
OpenAI Batch API를 사용하여 모든 문서에서 엔티티 추출

### 입력
- `data/raw/british_library/**/*_text.json`
- `data/raw/gutenberg/**/*.txt`
- `data/raw/arthurian/**/*.txt`

### 처리 방식
```
문서 → Batch Request → OpenAI gpt-5-nano → Structured JSON Output
```

### 출력 스키마
```json
{
  "persons": [
    {"name": "...", "role": "...", "birth_year": null, "death_year": null, "era": "...", "confidence": 0.9}
  ],
  "locations": [
    {"name": "...", "location_type": "...", "modern_name": "...", "confidence": 0.9}
  ],
  "polities": [
    {"name": "...", "polity_type": "...", "start_year": null, "end_year": null, "confidence": 0.9}
  ],
  "periods": [
    {"name": "...", "start_year": null, "end_year": null, "region": "...", "confidence": 0.9}
  ],
  "events": [
    {"name": "...", "year": null, "persons_involved": [], "locations_involved": [], "confidence": 0.9}
  ]
}
```

### 배치 설정
- **Chunk size**: 10,000 requests per batch
- **Model**: `gpt-5-nano` ($0.05/1M input, $0.40/1M output)
- **Token limit**: 40M enqueued tokens
- **Completion window**: 24h

### 비용
- Input: ~152M tokens × $0.05/1M = $7.60
- Output: ~38M tokens × $0.40/1M = $15.20
- **Total: ~$22.80**

### 결과 저장 위치
```
poc/data/integrated_ner_full/
├── batch_00.jsonl          # 배치 요청 파일
├── batch_00_output.jsonl   # 배치 결과 파일
├── ...
└── submission_status.json  # 배치 제출 상태
```

---

## Phase 2: Entity Organization (역정리)

### 목적
문서별 추출 결과를 엔티티 중심으로 재구성

### 2.1 JSON 파일 저장

#### 디렉토리 구조
```
poc/data/entities/
├── persons/
│   ├── index.json              # 전체 인물 목록 (이름, ID, 출현 횟수)
│   ├── a/
│   │   ├── alexander_the_great.json
│   │   ├── aristotle.json
│   │   └── ...
│   ├── b/
│   │   └── ...
│   └── ...
├── locations/
│   ├── index.json
│   └── {first_letter}/{normalized_name}.json
├── polities/
│   ├── index.json
│   └── {first_letter}/{normalized_name}.json
├── periods/
│   ├── index.json
│   └── {normalized_name}.json
└── events/
    ├── index.json
    └── {first_letter}/{normalized_name}.json
```

#### 개별 엔티티 파일 형식 (예: `persons/a/alexander_the_great.json`)
```json
{
  "id": "person_alexander_the_great",
  "canonical_name": "Alexander the Great",
  "aliases": ["Alexander III of Macedon", "Alexander of Macedonia"],
  "type": "person",
  "attributes": {
    "role": "King of Macedonia, Military Commander",
    "birth_year": -356,
    "death_year": -323,
    "era": "Classical Antiquity"
  },
  "mentions": [
    {
      "document_id": "british_library/000123456",
      "context": "Alexander the Great conquered Persia...",
      "confidence": 0.95,
      "extracted_at": "2026-01-06T12:00:00Z"
    },
    {
      "document_id": "gutenberg/12345",
      "context": "The campaigns of Alexander...",
      "confidence": 0.88,
      "extracted_at": "2026-01-06T12:00:00Z"
    }
  ],
  "related_entities": {
    "locations": ["Macedonia", "Persia", "Egypt", "Babylon"],
    "events": ["Battle of Gaugamela", "Siege of Tyre"],
    "periods": ["Hellenistic Period"]
  },
  "stats": {
    "mention_count": 245,
    "avg_confidence": 0.91,
    "first_seen": "2026-01-06",
    "last_updated": "2026-01-06"
  }
}
```

#### Index 파일 형식 (예: `persons/index.json`)
```json
{
  "total_count": 15234,
  "last_updated": "2026-01-06T12:00:00Z",
  "entities": [
    {"id": "person_alexander_the_great", "name": "Alexander the Great", "mention_count": 245, "file": "a/alexander_the_great.json"},
    {"id": "person_aristotle", "name": "Aristotle", "mention_count": 189, "file": "a/aristotle.json"},
    ...
  ]
}
```

### 2.2 PostgreSQL 저장

#### 테이블 스키마

```sql
-- 엔티티 기본 테이블
CREATE TABLE entities (
    id VARCHAR(255) PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- person, location, polity, period, event
    attributes JSONB,
    embedding vector(1536),  -- text-embedding-3-small
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 엔티티 별칭
CREATE TABLE entity_aliases (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(255) REFERENCES entities(id),
    alias TEXT NOT NULL,
    UNIQUE(entity_id, alias)
);

-- 문서 내 멘션
CREATE TABLE entity_mentions (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(255) REFERENCES entities(id),
    document_id VARCHAR(255) NOT NULL,
    context TEXT,
    confidence FLOAT,
    extracted_at TIMESTAMP DEFAULT NOW()
);

-- 엔티티 간 관계
CREATE TABLE entity_relations (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(255) REFERENCES entities(id),
    target_entity_id VARCHAR(255) REFERENCES entities(id),
    relation_type VARCHAR(100),  -- participated_in, located_in, part_of, contemporary_with
    confidence FLOAT,
    source_document_id VARCHAR(255)
);

-- 인덱스
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(canonical_name);
CREATE INDEX idx_entities_embedding ON entities USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_mentions_document ON entity_mentions(document_id);
CREATE INDEX idx_relations_source ON entity_relations(source_entity_id);
CREATE INDEX idx_relations_target ON entity_relations(target_entity_id);
```

### 2.3 처리 스크립트

```
poc/scripts/integrated_ner/
├── download_results.py     # 배치 결과 다운로드
├── organize_entities.py    # 엔티티 역정리 (JSON 생성)
├── deduplicate.py          # 중복 엔티티 병합
├── generate_embeddings.py  # 벡터 임베딩 생성
└── load_to_postgres.py     # PostgreSQL 로드
```

---

## Phase 3: Curating (Historical Chain)

### 목적
엔티티들을 연결하여 의미 있는 역사적 서사(Historical Chain) 생성

### 체인 유형
1. **Person Story**: 인물의 생애와 주요 사건
2. **Place Story**: 장소의 역사적 변천
3. **Era Story**: 시대의 인물, 장소, 사건 종합
4. **Causal Chain**: 인과관계로 연결된 사건 흐름

### 처리 흐름
```
엔티티 데이터 → 관계 분석 → LLM 체인 생성 → 검증 → 저장
```

### 체인 생성 모델
- Primary: `gpt-5-nano`
- Fallback: `gpt-5-mini`, `gpt-5.1-chat-latest`

### 출력 형식
```json
{
  "chain_id": "chain_alexander_conquest",
  "chain_type": "person_story",
  "title": "Alexander's Conquest of the Persian Empire",
  "summary": "...",
  "nodes": [
    {"type": "event", "id": "event_battle_of_granicus", "year": -334, "description": "..."},
    {"type": "event", "id": "event_battle_of_issus", "year": -333, "description": "..."},
    ...
  ],
  "edges": [
    {"from": 0, "to": 1, "relation": "led_to"},
    ...
  ],
  "related_chains": ["chain_hellenistic_kingdoms"],
  "sources": ["british_library/...", "gutenberg/..."]
}
```

---

## Phase 4: Serving (API)

### 엔드포인트

```
# 엔티티 검색
GET  /api/v1/entities?type=person&q=alexander
GET  /api/v1/entities/{entity_id}
GET  /api/v1/entities/{entity_id}/mentions
GET  /api/v1/entities/{entity_id}/relations

# 체인 조회
GET  /api/v1/chains?type=person_story&entity_id=...
GET  /api/v1/chains/{chain_id}

# 벡터 검색
POST /api/v1/search/semantic
     {"query": "battles in ancient Greece", "limit": 10}

# 시간/공간 필터
GET  /api/v1/entities?type=event&year_from=-500&year_to=-300&location=Greece
```

### 캐싱 전략
- Redis: 자주 조회되는 엔티티, 체인
- JSON 파일: 오프라인 백업, CDN 배포 가능

---

## Pipeline Execution Order

```
[Phase 1] NER Extraction
    ↓ (Batch API 완료)
[Phase 2.1] Download Results
    ↓
[Phase 2.2] Organize to JSON
    ↓
[Phase 2.3] Deduplicate & Merge
    ↓
[Phase 2.4] Generate Embeddings
    ↓
[Phase 2.5] Load to PostgreSQL
    ↓
[Phase 3] Generate Historical Chains
    ↓
[Phase 4] Serve via API
```

---

## Incremental Update Flow

새 문서 추가 시:

```
새 문서 → Phase 1 (NER) → Phase 2 (역정리)
                              ↓
            기존 엔티티와 매칭 → 업데이트 or 신규 생성
                              ↓
            관련 체인 재생성 트리거
```

### 업데이트 정책
1. 동일 엔티티 발견 시 `mentions` 배열에 추가
2. 새 별칭 발견 시 `aliases`에 추가
3. 신뢰도 높은 정보로 `attributes` 업데이트
4. `stats.last_updated` 갱신

---

## Current Status (2026-01-06)

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: NER Extraction | **Completed** | 76,008/76,019 (99.98%) |
| Phase 2: Entity Organization | Pending | 0% |
| Phase 3: Curating | Pending | 0% |
| Phase 4: Serving | Existing V0 API | - |

### Next Steps
1. Download batch results (8 output files)
2. Create `organize_entities.py` script
3. Run entity organization
4. Implement deduplication logic
5. Load to PostgreSQL

---

## Cost Summary

| Phase | Model | Estimated Cost |
|-------|-------|----------------|
| Phase 1: NER | gpt-5-nano (Batch) | ~$22.80 |
| Phase 2: Embeddings | text-embedding-3-small | ~$3.00 |
| Phase 3: Chains | gpt-5-nano | ~$5.00 |
| **Total** | | **~$30.80** |

---

## Files Reference

```
poc/scripts/integrated_ner/
├── batch_processor.py      # Phase 1: 배치 생성/제출
├── extractor.py            # LLM 추출기 (실시간용)
├── schema.py               # Pydantic 스키마
├── download_results.py     # Phase 2: 결과 다운로드
├── organize_entities.py    # Phase 2: 역정리
├── deduplicate.py          # Phase 2: 중복 제거
├── generate_embeddings.py  # Phase 2: 임베딩
└── load_to_postgres.py     # Phase 2: DB 로드

docs/logs/
├── BATCH_FAILURE_ANALYSIS_20260105.md  # 배치 실패 분석
└── NER_PIPELINE_LOG.md                 # 파이프라인 실행 로그
```
