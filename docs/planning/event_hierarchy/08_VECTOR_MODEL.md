# 이벤트 계층화 - 벡터 기반 역사 모델

**작성일**: 2026-01-28
**목적**: 이벤트를 방향성 벡터로 모델링하여 숨은 연결 발견 및 관계 자동 추론

---

## 1. 핵심 개념

### 1.1 이벤트 = 벡터

모든 역사적 사건은 **시작점(before)**과 **끝점(after)**을 가진 방향성 벡터.

```
          ┌─────────┐
    ──────│  Event  │──────▶
  before  └─────────┘  after

시간 축 ════════════════════════════════════════▶
```

### 1.2 엔티티와 벡터의 관계

```
Person (인물)
════════════════════════════════════════════════▶ 생애
    │       │          │              │
    ▼       ▼          ▼              ▼
  출생    교육       전투참여        사망
   E1      E2          E3            E4

→ Person = 자신을 통과하는 이벤트 벡터들의 집합
→ Person Story = 벡터 시퀀스 [E1 → E2 → E3 → E4]
```

```
Location (장소)
════════════════════════════════════════════════▶ 시간
    │       │          │              │
    ▼       ▼          ▼              ▼
  건설    전쟁발생    조약체결       파괴
   E1      E2          E3            E4

→ Location = 그곳을 통과하는 이벤트 벡터들의 기록
→ Place Story = 해당 장소의 벡터 시퀀스
```

### 1.3 Aggregate Event = 벡터 합성

```
백년전쟁 (Aggregate Vector)
══════════════════════════════════════════════▶

    ┌────────┐   ┌────────┐   ┌────────┐
───▶│ 크레시 │──▶│푸아티에│──▶│아쟁쿠르│───▶
    └────────┘   └────────┘   └────────┘

→ 합성 벡터 = 개별 벡터들의 방향 + 강도 종합
→ 합성 벡터의 영향력 = 하위 벡터들의 총합
```

---

## 2. 벡터 속성

### 2.1 이벤트 벡터 정의

```python
@dataclass
class EventVector:
    event_id: int

    # 시간적 속성
    start_year: int      # 벡터 시작점
    end_year: int        # 벡터 끝점
    duration: int        # 벡터 길이 (년)

    # 공간적 속성
    location_ids: List[int]  # 통과하는 장소들

    # 엔티티 연결
    person_ids: List[int]    # 관련 인물들

    # 벡터 강도
    importance: int      # 1-5
    influence_radius: float  # 영향 범위 (년)

    # 인과 관계 (벡터 방향)
    incoming_vectors: List[int]   # 이 벡터에 영향을 준 이벤트
    outgoing_vectors: List[int]   # 이 벡터가 영향을 준 이벤트
```

### 2.2 벡터 간 관계

| 관계 유형 | 설명 | 시각화 |
|----------|------|--------|
| **Sequential** | 시간순 연속 | E1 ──▶ E2 |
| **Causal** | 인과 관계 | E1 ═══▶ E2 |
| **Parallel** | 동시 발생 | E1 ∥ E2 |
| **Convergent** | 합류 | E1 ╲ E3 ╱ E2 |
| **Divergent** | 분기 | E1 ╱ E2 ╲ E3 |

---

## 3. 숨은 연결 발견

### 3.1 벡터 교차점 분석

```
인물 A의 벡터 흐름:  ──▶ E1 ──▶ E3 ──▶ E5 ──▶
인물 B의 벡터 흐름:  ──▶ E2 ──▶ E3 ──▶ E6 ──▶
                              ↑
                         교차점 발견!

→ "A와 B는 E3에서 만났을 가능성" (명시적 기록 없어도)
```

### 3.2 유사 벡터 패턴

```python
def find_similar_patterns(entity_a, entity_b):
    """두 엔티티의 벡터 패턴 유사도 분석"""
    vectors_a = get_event_vectors(entity_a)
    vectors_b = get_event_vectors(entity_b)

    # 1. 시간적 중첩
    temporal_overlap = calculate_temporal_overlap(vectors_a, vectors_b)

    # 2. 공간적 근접성
    spatial_proximity = calculate_spatial_proximity(vectors_a, vectors_b)

    # 3. 주제적 유사성 (카테고리, 키워드)
    thematic_similarity = calculate_thematic_similarity(vectors_a, vectors_b)

    # 종합 점수
    similarity = (temporal_overlap * 0.3 +
                  spatial_proximity * 0.3 +
                  thematic_similarity * 0.4)

    if similarity > 0.6:
        return {
            "hypothesis": f"{entity_a}와 {entity_b}는 연관이 있었을 가능성",
            "confidence": similarity,
            "shared_events": find_shared_events(vectors_a, vectors_b),
            "near_miss_events": find_near_miss_events(vectors_a, vectors_b)
        }
    return None
```

### 3.3 인과 체인 추론

```
E1 (종교개혁, 1517)
    │ influence: 0.9
    ▼
E2 (30년 전쟁, 1618)
    │ influence: 0.8
    ▼
E3 (베스트팔렌 조약, 1648)
    │ influence: 0.85
    ▼
E4 (주권국가 체제, 1648+)

→ 벡터 흐름 추적으로 장기적 인과 관계 시각화
```

---

## 4. 관계 자동 업데이트

### 4.1 새 문서 처리 시 벡터 분석

```python
async def run_post_processing(book_id: str, title: str):
    """기존 파이프라인 + 벡터 분석"""

    # 1. 기존: context 추출
    if post_process_settings["auto_context"]:
        extract_contexts_from_book(extraction_file)

    # 2. 기존: DB 매칭
    if post_process_settings["auto_db_match"]:
        match_book_entities(context_file, conn, stats)

    # 3. 신규: 벡터 기반 관계 분석
    if post_process_settings["auto_relations"]:
        analyze_vector_relationships(book_id, conn)
```

### 4.2 벡터 기반 관계 분석

```python
def analyze_vector_relationships(book_id: str, conn):
    """추출된 엔티티 간 벡터 관계 분석"""

    # 1. 이 책에서 추출된 엔티티들
    extraction = load_extraction(book_id)
    persons = extraction["persons"]
    events = extraction["events"]

    # 2. 각 엔티티의 기존 벡터 로드
    for person in persons:
        person_vectors = get_person_vectors(person, conn)

        # 3. 다른 엔티티와의 벡터 교차점 찾기
        for other_person in persons:
            if person == other_person:
                continue

            other_vectors = get_person_vectors(other_person, conn)
            intersections = find_vector_intersections(
                person_vectors, other_vectors
            )

            # 4. 관계 생성 또는 confidence 업데이트
            for intersection in intersections:
                update_or_create_relationship(
                    person, other_person,
                    relation_type="co_occurrence",
                    strength=intersection["strength"],
                    evidence=f"Book: {book_id}"
                )
```

### 4.3 관계 Confidence 재계산

```python
def recalculate_relationship_confidence(rel, new_evidence):
    """새 증거로 관계 confidence 재계산"""

    old_conf = rel.confidence
    evidence_count = len(rel.sources) + 1

    # 베이지안 업데이트 (단순화)
    # 더 많은 출처 → 더 높은 confidence
    new_conf = min(0.99, old_conf + (1 - old_conf) * 0.1 * evidence_count)

    # 모순 증거가 있으면 감소
    if is_contradicting(new_evidence, rel):
        new_conf = max(0.1, old_conf * 0.7)
        rel.disputed = True

    return new_conf
```

---

## 5. 데이터 구조

### 5.1 기존 테이블 활용

벡터 모델은 새 테이블 없이 기존 구조를 쿼리로 활용:

```sql
-- 인물의 벡터 시퀀스 (통과하는 이벤트들)
SELECT e.id, e.title, e.date_start, e.date_end
FROM events e
JOIN event_persons ep ON e.id = ep.event_id
WHERE ep.person_id = :person_id
ORDER BY e.date_start;

-- 두 인물의 벡터 교차점 (공유 이벤트)
SELECT e.id, e.title
FROM events e
JOIN event_persons ep1 ON e.id = ep1.event_id
JOIN event_persons ep2 ON e.id = ep2.event_id
WHERE ep1.person_id = :person_a_id
  AND ep2.person_id = :person_b_id;

-- 장소의 벡터 시퀀스 (거쳐간 이벤트들)
SELECT e.id, e.title, e.date_start
FROM events e
JOIN event_locations el ON e.id = el.event_id
WHERE el.location_id = :location_id
ORDER BY e.date_start;
```

### 5.2 캐시 테이블 (성능 최적화용, 선택적)

```sql
-- 벡터 교차점 캐시 (자주 조회되는 경우)
CREATE TABLE vector_intersections (
    entity_a_type VARCHAR(20),
    entity_a_id INTEGER,
    entity_b_type VARCHAR(20),
    entity_b_id INTEGER,
    intersection_count INTEGER,
    shared_event_ids INTEGER[],
    similarity_score FLOAT,
    last_calculated TIMESTAMP,
    PRIMARY KEY (entity_a_type, entity_a_id, entity_b_type, entity_b_id)
);
```

---

## 6. API 엔드포인트

```python
# 인물/장소의 벡터 시퀀스
GET /api/v1/persons/{id}/vector
GET /api/v1/locations/{id}/vector

# 두 엔티티 간 벡터 분석
GET /api/v1/vectors/intersection?a_type=person&a_id=1&b_type=person&b_id=2

# 숨은 연결 발견
GET /api/v1/vectors/discover?entity_type=person&entity_id=1&threshold=0.6

# 인과 체인 추적
GET /api/v1/vectors/causal-chain?event_id=1&direction=both&max_depth=5
```

---

## 7. 프론트엔드 시각화

### 7.1 벡터 타임라인

```
인물: 알렉산더 대왕
════════════════════════════════════════════════▶

BCE 356   BCE 336        BCE 334-323              BCE 323
   │         │                │                      │
   ▼         ▼                ▼                      ▼
 ┌────┐   ┌────────┐   ┌─────────────────┐      ┌────┐
 │출생│   │즉위    │   │ 동방 원정       │      │사망│
 └────┘   └────────┘   └─────────────────┘      └────┘
                            ↓ 포함
            ┌────────┬────────┬────────┬────────┐
            │그라니코│이소스  │가우가멜│히다스페│
            └────────┴────────┴────────┴────────┘
```

### 7.2 벡터 네트워크 그래프

```
              ┌─────────────┐
              │  계몽주의   │
              └──────┬──────┘
          ┌──────────┼──────────┐
          ▼          ▼          ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │미국 독립 │ │프랑스혁명│ │산업혁명  │
   └────┬─────┘ └────┬─────┘ └────┬─────┘
        │            │            │
        └────────────┼────────────┘
                     ▼
              ┌──────────────┐
              │ 1848년 혁명들│
              └──────────────┘
```

---

## 8. 구현 우선순위

### Phase 1: 쿼리 기반 벡터 분석
- [ ] 인물/장소 벡터 시퀀스 조회 API
- [ ] 벡터 교차점 찾기 API
- [ ] 기본 유사도 계산

### Phase 2: 파이프라인 통합
- [ ] `run_post_processing`에 관계 분석 단계 추가
- [ ] 새 문서 처리 시 자동 관계 업데이트
- [ ] confidence 재계산 로직

### Phase 3: 시각화
- [ ] 벡터 타임라인 컴포넌트
- [ ] 인과 체인 그래프 뷰

---

## 9. Historical Chain과의 연계

벡터 모델은 V1 Historical Chain의 기반:

| V1 Chain 유형 | 벡터 모델 대응 |
|--------------|---------------|
| Person Story | 인물을 통과하는 벡터 시퀀스 |
| Place Story | 장소를 통과하는 벡터 시퀀스 |
| Era Story | 특정 시간 범위의 모든 벡터 |
| Causal Chain | 인과 관계로 연결된 벡터 그래프 |
