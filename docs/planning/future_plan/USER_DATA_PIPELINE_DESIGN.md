# User Data Pipeline Design

> **상태**: 설계 검토
> **작성일**: 2026-01-12
> **관련**: `USER_DATA_CONTRIBUTION.md`, `NER_PIPELINE_DESIGN.md`

---

## 목표

사용자 업로드 데이터를 청킹하고, 각 청크에서 **Person/Event/Location을 추출**하여 **완전한 링크가 형성된 임시 데이터**를 생성한 후, 기존 World State에 병합.

---

## 핵심 인사이트

### "같은 청크 = 잠재적 관계"

```
청크 예시:
"알렉산더 대왕은 기원전 334년 그라니쿠스 전투에서 페르시아군을 물리쳤다.
 그의 장군 파르메니온이 좌익을 지휘했다."

추출 결과:
├── Person: 알렉산더 대왕
├── Person: 파르메니온
├── Event: 그라니쿠스 전투
├── Location: (그라니쿠스 - 암시적)
├── Time: 기원전 334년

동시 출현 → 관계 추론:
├── 알렉산더 ↔ 그라니쿠스 전투 (참여)
├── 파르메니온 ↔ 그라니쿠스 전투 (참여)
├── 알렉산더 ↔ 파르메니온 (동시대, 상하관계 암시)
```

**이것이 Historical Chain의 연결고리가 됨.**

---

## 파이프라인 설계

### Stage 1: 문서 수집 & 전처리

```
입력: PDF, TXT, DOCX, 이미지, CSV, JSON
            ↓
┌─────────────────────────────────────┐
│ 1.1 포맷 감지 & 변환                 │
│     - PDF → PyMuPDF 텍스트 추출      │
│     - 이미지 → Tesseract OCR         │
│     - DOCX → python-docx            │
│     - 구조화 데이터 → 직접 파싱       │
└─────────────────────────────────────┘
            ↓
┌─────────────────────────────────────┐
│ 1.2 메타데이터 추출                  │
│     - 문서 제목, 저자, 날짜          │
│     - 섹션 구조 (목차, 헤딩)         │
│     - 언어 감지                      │
└─────────────────────────────────────┘
            ↓
        정제된 텍스트 + 메타데이터
```

### Stage 2: 시맨틱 청킹

**왜 시맨틱 청킹인가?**
- 고정 크기 청킹: 문장 중간에 끊김 → 컨텍스트 손실
- 시맨틱 청킹: 의미 단위 보존 → 엔티티 관계 유지

```python
# 청킹 전략
class ChunkingStrategy:
    # 1순위: 섹션/챕터 단위
    # 2순위: 문단 단위 (빈 줄 기준)
    # 3순위: 문장 그룹 (5-10문장)

    max_chunk_size = 1500  # 토큰
    min_chunk_size = 200   # 토큰
    overlap = 100          # 경계 컨텍스트 보존
```

**청크 구조:**
```json
{
  "chunk_id": "doc123_chunk_007",
  "document_id": "doc123",
  "sequence": 7,
  "text": "알렉산더 대왕은 기원전 334년...",
  "char_start": 4520,
  "char_end": 5890,
  "section": "Chapter 3: Persian Campaign",
  "overlap_prev": "...다리우스 3세는",
  "overlap_next": "이후 이수스 전투에서..."
}
```

---

### Stage 3: 청크별 엔티티 추출 (NER)

각 청크를 독립적으로 처리:

```
청크 텍스트
    ↓
┌─────────────────────────────────────┐
│ 3.1 spaCy NER (1차)                 │
│     - PERSON, GPE, LOC, DATE, ORG   │
│     - 빠름, 저비용                   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3.2 GPT-nano 검증 & 보강 (2차)      │
│     - 역사적 맥락 이해               │
│     - 암시적 엔티티 추출             │
│     - 역할/관계 추론                 │
└─────────────────────────────────────┘
    ↓
청크별 엔티티 목록
```

**추출 결과 구조:**
```json
{
  "chunk_id": "doc123_chunk_007",
  "entities": [
    {
      "temp_id": "ent_001",
      "text": "알렉산더 대왕",
      "type": "PERSON",
      "char_start": 0,
      "char_end": 7,
      "confidence": 0.95,
      "attributes": {
        "role": "commander",
        "title": "king"
      }
    },
    {
      "temp_id": "ent_002",
      "text": "그라니쿠스 전투",
      "type": "EVENT",
      "char_start": 25,
      "char_end": 33,
      "confidence": 0.92,
      "attributes": {
        "event_type": "battle",
        "year": -334
      }
    }
  ]
}
```

---

### Stage 4: 동시출현 기반 관계 추출

**핵심**: 같은 청크에 등장한 엔티티들은 관계가 있을 가능성 높음

```
┌─────────────────────────────────────┐
│ 4.1 동시출현 매트릭스 생성           │
│                                     │
│     청크 007:                       │
│     알렉산더 ─── 그라니쿠스 전투    │
│         │              │            │
│         └── 파르메니온 ─┘           │
│                                     │
│     → 3개 엔티티 간 3개 잠재 관계   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4.2 관계 유형 추론 (GPT)            │
│                                     │
│     입력: "알렉산더 대왕은...        │
│            파르메니온이 좌익을..."   │
│                                     │
│     추론:                           │
│     - 알렉산더 → 그라니쿠스: 참여자 │
│     - 파르메니온 → 그라니쿠스: 참여자│
│     - 알렉산더 → 파르메니온: 상관   │
└─────────────────────────────────────┘
```

**관계 구조:**
```json
{
  "chunk_id": "doc123_chunk_007",
  "relationships": [
    {
      "source_temp_id": "ent_001",  // 알렉산더
      "target_temp_id": "ent_002",  // 그라니쿠스 전투
      "relation_type": "participated_in",
      "role": "commander",
      "confidence": 0.88,
      "evidence_span": "알렉산더 대왕은...물리쳤다"
    },
    {
      "source_temp_id": "ent_001",  // 알렉산더
      "target_temp_id": "ent_003",  // 파르메니온
      "relation_type": "commanded",
      "confidence": 0.75,
      "evidence_span": "그의 장군 파르메니온"
    }
  ]
}
```

---

### Stage 5: 임시 데이터 통합

모든 청크의 결과를 문서 레벨로 통합:

```
┌─────────────────────────────────────┐
│ 5.1 엔티티 통합 (문서 내)           │
│                                     │
│     청크 007: "알렉산더 대왕"       │
│     청크 008: "알렉산더"            │
│     청크 012: "대왕"                │
│                                     │
│     → 동일 인물로 병합              │
│     → temp_id 통일: ent_001        │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5.2 관계 통합 & 강화                │
│                                     │
│     여러 청크에서 같은 관계 발견 시:│
│     confidence *= 1.2 (강화)        │
│                                     │
│     충돌 관계 발견 시:              │
│     두 관계 모두 보존 + 플래그      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5.3 임시 데이터 구조 생성           │
│                                     │
│     StagingDocument {               │
│       entities: [...]               │
│       relationships: [...]          │
│       source_info: {...}            │
│       quality_tier: 4               │
│     }                               │
└─────────────────────────────────────┘
```

**임시 데이터 스키마:**
```sql
-- 스테이징 테이블 (병합 전 임시 저장)
CREATE TABLE staging_documents (
    id SERIAL PRIMARY KEY,
    upload_id UUID,
    uploader_id INTEGER,
    original_filename VARCHAR(255),
    processed_at TIMESTAMP,
    status VARCHAR(50),  -- 'pending', 'processing', 'ready', 'merged', 'rejected'
    quality_tier INTEGER DEFAULT 4
);

CREATE TABLE staging_entities (
    id SERIAL PRIMARY KEY,
    staging_doc_id INTEGER REFERENCES staging_documents(id),
    temp_id VARCHAR(50),
    entity_type VARCHAR(50),  -- PERSON, EVENT, LOCATION
    name VARCHAR(255),
    attributes JSONB,
    confidence FLOAT,
    matched_entity_id INTEGER,  -- NULL if new, ID if matched to existing
    match_confidence FLOAT
);

CREATE TABLE staging_relationships (
    id SERIAL PRIMARY KEY,
    staging_doc_id INTEGER REFERENCES staging_documents(id),
    source_temp_id VARCHAR(50),
    target_temp_id VARCHAR(50),
    relation_type VARCHAR(100),
    confidence FLOAT,
    evidence_text TEXT,
    chunk_ids TEXT[]  -- 어느 청크들에서 발견되었는지
);
```

---

### Stage 6: 기존 DB 매칭

임시 엔티티를 기존 World State와 매칭:

```
┌─────────────────────────────────────┐
│ 6.1 후보 검색                       │
│                                     │
│     임시: "알렉산더 대왕"           │
│                                     │
│     검색 방법:                      │
│     1. 정확 매칭 (name)             │
│     2. 유사도 매칭 (trigram)        │
│     3. 별칭 매칭 (aliases)          │
│     4. 벡터 검색 (embedding)        │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 6.2 매칭 결정                       │
│                                     │
│     매칭 신뢰도 > 0.9:              │
│       → 자동 연결                   │
│                                     │
│     매칭 신뢰도 0.7-0.9:            │
│       → 큐레이터 검토 대기          │
│                                     │
│     매칭 후보 없음:                 │
│       → 신규 엔티티 생성 대기       │
└─────────────────────────────────────┘
```

---

### Stage 7: 병합 & World State 업데이트

```
┌─────────────────────────────────────┐
│ 7.1 검토 & 승인                     │
│                                     │
│     자동 승인 조건:                 │
│     - 모든 엔티티 매칭 신뢰도 > 0.9 │
│     - 충돌 관계 없음                │
│     - 품질 점수 > threshold         │
│                                     │
│     수동 검토 필요:                 │
│     - 낮은 신뢰도 매칭             │
│     - 신규 엔티티 생성             │
│     - 기존 데이터와 충돌           │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 7.2 World State 병합                │
│                                     │
│     1. 신규 엔티티 생성 (Tier 4)    │
│     2. 기존 엔티티에 출처 추가      │
│     3. event_connections 생성      │
│     4. 소스 레퍼런스 저장           │
│     5. 업로더 귀속 표시 추가        │
└─────────────────────────────────────┘
```

---

## 데이터 흐름 요약

```
사용자 문서
    │
    ▼
┌───────────┐
│ Stage 1   │ 전처리 & 메타데이터
└───────────┘
    │
    ▼
┌───────────┐
│ Stage 2   │ 시맨틱 청킹 (1500 토큰 단위)
└───────────┘
    │
    ▼ (청크 N개)
┌───────────┐
│ Stage 3   │ 청크별 NER (Person, Event, Location)
└───────────┘
    │
    ▼
┌───────────┐
│ Stage 4   │ 동시출현 기반 관계 추출
└───────────┘
    │
    ▼
┌───────────┐
│ Stage 5   │ 임시 데이터 통합 (StagingDocument)
└───────────┘
    │
    ▼
┌───────────┐
│ Stage 6   │ 기존 DB 매칭 (fuzzy + vector)
└───────────┘
    │
    ▼
┌───────────┐
│ Stage 7   │ 검토 → 승인 → World State 병합
└───────────┘
```

---

## 핵심 설계 결정

### 1. 왜 청크 단위인가?

| 접근법 | 장점 | 단점 |
|--------|------|------|
| 문서 전체 | 전체 맥락 | 토큰 제한, 비용 |
| 문장 단위 | 세밀함 | 관계 추출 어려움 |
| **청크 단위** | 균형, 관계 보존 | 경계 처리 필요 |

### 2. 왜 동시출현 기반인가?

- **언어학적 근거**: 같은 문단에 언급 = 의미적 연관
- **Historical Chain 자연 생성**: 추가 로직 없이 관계 추출
- **확장성**: LLM 의존도 낮춤 (비용 절감)

### 3. 왜 Staging 테이블인가?

- **Immutable Core 원칙**: 직접 수정 없음
- **롤백 가능**: 문제 발생 시 staging만 삭제
- **검토 워크플로우**: 승인 전 검토 가능
- **배치 처리**: 여러 문서 동시 처리

---

## 품질 보장 메커니즘

### 1. 자동 검증

```python
def validate_staging_document(doc):
    checks = [
        # 엔티티 최소 개수
        len(doc.entities) >= 3,

        # 관계 최소 개수
        len(doc.relationships) >= 1,

        # 평균 신뢰도
        avg_confidence(doc.entities) >= 0.7,

        # 중복 검사
        not is_duplicate(doc),

        # 스팸/노이즈 검사
        not is_spam(doc.text),
    ]
    return all(checks)
```

### 2. 수동 검토 큐

```
검토 대기열:
├── 높은 우선순위: 신규 엔티티 생성 요청
├── 중간 우선순위: 낮은 매칭 신뢰도
└── 낮은 우선순위: 기존 데이터 보강
```

### 3. 커뮤니티 검증 (Tier 3 → Tier 2)

```
Tier 3 데이터:
├── 최소 3명의 긍정 평가
├── 전문가 1명 승인
└── 30일 무이의 → Tier 2 승격
```

---

## 예상 비용 (1000 페이지 문서 기준)

| 단계 | 모델 | 비용 |
|------|------|------|
| OCR | Tesseract | $0 (로컬) |
| NER 1차 | spaCy | $0 (로컬) |
| NER 2차 | GPT-nano | ~$0.50 |
| 관계 추론 | GPT-nano | ~$1.00 |
| 매칭 검증 | GPT-nano | ~$0.30 |
| **총계** | | **~$1.80** |

---

## 다음 단계

1. **프로토타입**: 단일 문서 파이프라인 구현
2. **테스트**: 위키피디아 문서로 검증
3. **스케일**: 배치 처리, 큐 시스템
4. **UI**: 업로드 인터페이스, 검토 대시보드

---

## 미해결 질문

1. **청크 크기 최적화**: 1500 토큰이 최적인가?
2. **언어 혼합**: 한국어/영어 혼합 문서 처리?
3. **이미지 내 텍스트**: OCR 품질 보장 방법?
4. **실시간 vs 배치**: 즉시 처리 vs 야간 배치?

---

## 관련 문서

- `USER_DATA_CONTRIBUTION.md` - 비전 문서
- `NER_PIPELINE_DESIGN.md` - NER 상세 설계
- `HISTORICAL_CHAIN_CONCEPT.md` - Historical Chain 개념
