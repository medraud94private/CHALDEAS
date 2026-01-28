# 소스 기반 데이터 수집 파이프라인

## 핵심 원칙

**새 소스가 들어오면 → 엔티티 추출 → 기존 매칭 → 없으면 생성 → 관계 연결**

모든 관계는 **소스(출처)**를 통해 연결됨. 소스 없이 관계 생성 금지.

---

## 시나리오별 처리

### Case 1: 기존 엔티티만 있는 경우

**예시**: "아인슈타인과 괴델의 대화록" (장소: 취리히)

```
입력 소스: 책/문서
  ↓
NER 추출:
  - Person: Albert Einstein ✓ (DB 존재)
  - Person: Kurt Gödel ✓ (DB 존재)
  - Location: Zurich ✓ (DB 존재)
  ↓
처리:
  1. source 테이블에 새 소스 추가
  2. person_sources: Einstein ← 소스
  3. person_sources: Gödel ← 소스
  4. location_sources: Zurich ← 소스
  5. person_relationships: Einstein ↔ Gödel (source_id 포함)
  6. person_locations: Einstein → Zurich, Gödel → Zurich (source_id 포함)
```

### Case 2: 신규 엔티티 + 기존 엔티티 혼합

**예시**: "알퍼, 베테, 가모브의 화학 원소의 기원 발표회" (피렌체)
- 알퍼(Alpher): DB에 없음
- 베테(Bethe): DB에 있음
- 가모브(Gamow): DB에 있음
- 피렌체(Florence): DB에 있음

```
입력 소스: 책/문서
  ↓
NER 추출 및 매칭:
  - Person: Ralph Alpher ✗ (DB 없음) → 생성 필요
  - Person: Hans Bethe ✓ (DB 존재)
  - Person: George Gamow ✓ (DB 존재)
  - Location: Florence ✓ (DB 존재)
  - Event: "Origin of Chemical Elements presentation" ✗ → 생성 필요
  ↓
처리:
  1. source 테이블에 새 소스 추가

  2. Person 생성: Ralph Alpher
     - name, birth_year, death_year, description
     - wikidata_id 검색 → 연결
     - wikipedia_url 검색 → 연결

  3. Event 생성: "화학 원소의 기원 발표회"
     - date_start, date_end
     - description
     - 관련 소스 연결

  4. 관계 생성 (모두 source_id 포함):
     - person_relationships: Alpher ↔ Bethe ↔ Gamow
     - event_persons: Event ← Alpher, Bethe, Gamow
     - event_locations: Event → Florence
     - person_locations: 각 인물 → Florence

  5. 추가 연결 (있는 경우):
     - "빅뱅 이론" 이벤트/소스가 있으면 연결
     - Alpher-Bethe-Gamow paper 관련 소스 연결
```

### Case 3: 완전히 새로운 엔티티만

**예시**: 새로운 인물/사건이 모두 DB에 없는 경우

```
처리:
  1. source 추가
  2. 모든 엔티티 신규 생성 (Person, Event, Location)
  3. 각 엔티티에 source 연결
  4. 엔티티 간 관계 생성 (source_id 포함)
  5. Wikidata/Wikipedia 자동 매칭 시도
```

---

## 파이프라인 단계

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: 소스 등록                                              │
│  - 새 책/문서를 source 테이블에 등록                              │
│  - source_type: book, article, document, etc.                   │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: DB 기반 엔티티 매칭 (공짜, 빠름)                         │
│  - DB에서 모든 엔티티 이름 로드 (persons, locations, events)       │
│  - 텍스트에서 DB 이름 검색 (단순 문자열 매칭)                       │
│  - 매칭된 엔티티 → 바로 연결                                       │
│  - 비용: $0 (DB 쿼리 + 문자열 검색)                                │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3: 신규 엔티티 추출 (LLM)                                  │
│  - DB에 없는 엔티티만 LLM이 추출                                   │
│  - "이 텍스트에서 DB에 없는 인물/장소/사건 찾아줘"                   │
│  - 컨텍스트 이해: 동명이인, 새 인물 여부 판단                        │
│  - 비용: ~$0.001/1K tokens (신규만 처리하니까 적음)                 │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4: 신규 엔티티 생성                                        │
│  - NEW로 분류된 엔티티 생성                                       │
│  - Wikidata에서 메타데이터 보강                                   │
│  - Wikipedia에서 description 가져오기                             │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5: 관계 생성                                              │
│  - 같은 소스에 언급된 엔티티 간 관계 생성                          │
│  - relationship_type: co_mentioned, participated, etc.          │
│  - source_id 필수 포함 (출처 추적)                                │
│  - strength 계산 (시대, 장소, 공유소스 기반)                       │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 6: 기존 관계 보강                                         │
│  - 기존 관계에 새 소스 추가                                       │
│  - strength 재계산                                               │
│  - 관계 증거(evidence) 추가                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 데이터 모델 요구사항

### 필수 컬럼

```sql
-- 모든 관계 테이블에 필수
source_id       -- 관계를 생성한 소스 (FK to sources)
created_at      -- 생성 시점

-- 엔티티 테이블 (persons, events, locations)에 매칭 정보
match_score     -- DB 매칭 시 신뢰도 (0.0 ~ 1.0), 신규 생성이면 NULL
matched_by      -- 매칭 방법: 'wikidata_id', 'name_fuzzy', 'manual' 등

-- sources 테이블 필수
id, title, source_type, content, url, created_at
```

### 관계 테이블 예시

```sql
-- person_relationships
CREATE TABLE person_relationships (
    person1_id INT REFERENCES persons(id),
    person2_id INT REFERENCES persons(id),
    relationship_type VARCHAR(50),
    source_id INT REFERENCES sources(id),  -- 필수!
    strength FLOAT,
    confidence FLOAT,
    temporal_type VARCHAR(50),  -- contemporary / historical_reference
    created_at TIMESTAMP
);
```

---

## 구현 우선순위

| 단계 | 설명 | 상태 |
|-----|------|------|
| 1 | 소스 등록 API | 기존 있음 |
| 2 | NER 추출 (spaCy + LLM) | 기존 있음 |
| 3 | 기존 DB 매칭 로직 | 부분 구현 |
| 4 | 신규 엔티티 자동 생성 | **미구현** |
| 5 | 관계 자동 생성 (source_id 포함) | 부분 구현 |
| 6 | 기존 관계 보강 | **미구현** |

---

## 다음 작업

### 즉시 필요
1. **신규 엔티티 자동 생성 스크립트**
   - NER 결과 → DB 매칭 실패 → 자동 생성
   - Wikidata 연동으로 메타데이터 보강

2. **관계 생성 시 source_id 필수화**
   - 기존 스크립트 수정
   - 출처 없는 관계 생성 방지

3. **매칭 신뢰도 시스템**
   - 동명이인 구분
   - 애매한 매칭 수동 검토 큐

### 향후 계획
- 일괄 소스 처리 CLI
- 관계 보강 자동화
- 수동 검토 UI

---

## 관련 파일

- `poc/scripts/import_to_v1_db.py` - 기존 임포트 스크립트
- `poc/scripts/create_relationships_from_links.py` - 링크 기반 관계
- `poc/scripts/create_relationships_from_mentions_v2.py` - 언급 기반 관계
- `backend/app/core/logos/` - LLM 연동
