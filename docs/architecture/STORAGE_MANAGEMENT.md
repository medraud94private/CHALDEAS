# Storage Management (저장고 관리) 설계

> 왜 규칙 기반이 위험하고, 어떻게 신뢰할 수 있는 저장고를 만드는가

---

## 1. 문제 정의

### 1.1 규칙 기반 자동 처리의 위험성

**"Louis XIV"와 "Louis XV"를 이름 유사도로 병합하면?**

```
입력 텍스트: "Louis XIV established Versailles..."
입력 텍스트: "Louis XV continued the tradition..."

❌ 규칙 기반 (이름 유사도 > 0.8):
   → "Louis" 85% 일치 → 병합!
   → 결과: 두 명의 다른 왕이 하나로 합쳐짐

✅ 올바른 처리:
   → 문맥 분석: XIV (14세) ≠ XV (15세)
   → 시대 확인: 1643-1715 ≠ 1715-1774
   → 결과: 별개의 Person 엔티티로 생성
```

### 1.2 더 많은 위험 케이스

| 케이스 | 입력 | 규칙 기반 결과 | 올바른 결과 |
|--------|------|---------------|------------|
| **세대 구분** | Henry VII, Henry VIII | 병합 (Henry 일치) | 별개 인물 |
| **동명이인** | Plato (철학자), Plato (희극작가) | 병합 | 별개 인물 |
| **지명 vs 사건** | Marathon (지명), Marathon (전투) | 혼동 | Location + Event |
| **별명** | "철혈재상", "Bismarck" | 별개로 생성 | 병합 필요 |
| **언어 차이** | "孔子", "Confucius" | 별개로 생성 | 병합 필요 |
| **시대 중복** | Napoleon I, Napoleon III | 병합 위험 | 별개 인물 |

---

## 2. 해결 방향: 문맥 기반 Archivist

### 2.1 핵심 원칙

```
규칙: "이름이 비슷하면 같은 엔티티다" → ❌ 위험
문맥: "이 텍스트에서 언급된 인물의 시대, 역할, 관계를 보고 판단" → ✅ 안전
```

### 2.2 Archivist의 역할

Archivist는 저장고의 문지기로, 새로운 데이터가 들어올 때:

1. **문맥 분석**: 텍스트 전체를 읽고 엔티티의 특성 파악
2. **기존 데이터 검색**: 유사한 기존 엔티티 후보 조회
3. **결정**: 새로 생성 / 기존에 연결 / 보류(사람 검토)
4. **기록**: 결정 이유와 신뢰도 저장

```
┌─────────────────────────────────────────────────────────────┐
│                    Archivist 처리 흐름                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [새 텍스트] → [NER 추출] → [Archivist 판단] → [저장소]       │
│                                  │                          │
│                                  ▼                          │
│                    ┌─────────────────────────┐              │
│                    │ 결정 유형:                │              │
│                    │ • CREATE_NEW (신규)      │              │
│                    │ • LINK_EXISTING (연결)   │              │
│                    │ • PENDING (보류)         │              │
│                    └─────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 상세 설계

### 3.1 엔티티 매칭 컨텍스트

NER이 추출한 각 엔티티에 대해 수집하는 정보:

```python
class EntityContext:
    # 기본 정보
    text: str              # 원문에서 추출된 텍스트 ("Louis XIV")
    entity_type: str       # person, location, event, time

    # 문맥 정보
    surrounding_text: str  # 앞뒤 500자
    co_occurring_entities: list  # 같이 언급된 다른 엔티티들

    # 시간 정보 (추론)
    implied_year_start: int | None  # 문맥에서 추론된 시작 연도
    implied_year_end: int | None    # 문맥에서 추론된 종료 연도

    # 역할/특성
    roles: list[str]       # ["king", "france", "absolute monarchy"]
    attributes: dict       # {"dynasty": "Bourbon", "ordinal": "XIV"}

    # 출처
    source_id: str
    source_reliability: float  # 출처 신뢰도
```

### 3.2 후보 검색 및 점수화

```python
class CandidateMatch:
    existing_entity_id: int
    match_scores: dict
    total_score: float
    decision: str  # CREATE_NEW, LINK_EXISTING, PENDING
    reasoning: str

def find_candidates(context: EntityContext) -> list[CandidateMatch]:
    """
    1단계: 후보 검색 (넓게)
    - 이름 유사도 > 0.5인 모든 엔티티
    - 벡터 유사도 상위 20개
    - 같은 시대 (±100년) 엔티티

    2단계: 상세 점수화 (좁게)
    """
    candidates = []

    # 이름 검색
    name_matches = search_by_name_similarity(context.text, threshold=0.5)

    # 벡터 검색 (문맥 임베딩)
    vector_matches = search_by_embedding(context.surrounding_text, top_k=20)

    # 시대 검색
    if context.implied_year_start:
        time_matches = search_by_time_range(
            context.implied_year_start - 100,
            context.implied_year_end + 100 if context.implied_year_end else context.implied_year_start + 100
        )

    # 중복 제거 후 점수화
    all_candidates = merge_unique(name_matches, vector_matches, time_matches)

    for candidate in all_candidates:
        scores = calculate_match_scores(context, candidate)
        candidates.append(CandidateMatch(
            existing_entity_id=candidate.id,
            match_scores=scores,
            total_score=weighted_sum(scores),
            decision=determine_decision(scores),
            reasoning=generate_reasoning(context, candidate, scores)
        ))

    return sorted(candidates, key=lambda c: c.total_score, reverse=True)
```

### 3.3 점수 체계 (가중치)

```python
MATCH_WEIGHTS = {
    # 이름 관련 (30%)
    "name_exact": 0.15,           # 정확히 일치
    "name_similarity": 0.10,      # Levenshtein/Jaro-Winkler
    "name_alias": 0.05,           # 별명/다른 표기 매칭

    # 시간 관련 (25%)
    "time_overlap": 0.15,         # 생몰년/발생시기 겹침
    "time_proximity": 0.10,       # 시간적 근접성

    # 문맥 관련 (30%)
    "context_similarity": 0.15,   # 문맥 벡터 유사도
    "co_occurrence": 0.10,        # 같이 언급되는 엔티티 일치
    "role_match": 0.05,           # 역할/직함 일치

    # 특수 속성 (15%)
    "ordinal_match": 0.10,        # 세대 구분 (I, II, XIV 등)
    "location_match": 0.05,       # 관련 지역 일치
}

# 결정 임계값
THRESHOLDS = {
    "LINK_EXISTING": 0.85,   # 85% 이상 → 자동 연결
    "PENDING": 0.60,         # 60-85% → 사람 검토
    "CREATE_NEW": 0.60,      # 60% 미만 → 새로 생성
}
```

### 3.4 세대 구분 (Ordinal) 특수 처리

```python
def check_ordinal_conflict(text1: str, text2: str) -> bool:
    """
    Louis XIV vs Louis XV → True (충돌)
    Henry VIII vs Henry VIII → False (일치)
    Napoleon vs Napoleon → False (구분자 없음)
    """
    ordinal_pattern = r'(I{1,3}|IV|V?I{0,3}|IX|X{0,3}|[0-9]+)$|(\d+세)$|(\d+世)$'

    ord1 = extract_ordinal(text1)
    ord2 = extract_ordinal(text2)

    if ord1 is None or ord2 is None:
        return False  # 구분자 없으면 충돌 아님

    return ord1 != ord2  # 다르면 충돌

# 세대 구분이 있고 다르면 → 절대 병합하지 않음
if check_ordinal_conflict(new_entity.text, candidate.name):
    return Decision.CREATE_NEW, "세대 구분자가 다름 (XIV ≠ XV)"
```

---

## 4. Archivist 구현

### 4.1 LLM 기반 판단

```python
class Archivist:
    def __init__(self, model: str = "qwen3:8b"):
        self.model = model
        self.ollama_client = OllamaClient()

    async def decide(
        self,
        new_context: EntityContext,
        candidates: list[CandidateMatch]
    ) -> ArchivistDecision:

        # 규칙 기반 사전 필터링
        # 세대 구분 충돌 → 즉시 CREATE_NEW
        for candidate in candidates:
            if check_ordinal_conflict(new_context.text, candidate.name):
                candidates.remove(candidate)

        if not candidates:
            return ArchivistDecision(
                decision="CREATE_NEW",
                confidence=0.95,
                reasoning="기존 엔티티 중 일치하는 후보 없음"
            )

        # LLM 판단 요청
        prompt = self._build_prompt(new_context, candidates)
        response = await self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            format="json"
        )

        return self._parse_response(response)

    def _build_prompt(self, context: EntityContext, candidates: list) -> str:
        return f"""
당신은 역사 데이터베이스의 Archivist입니다.
새로 추출된 엔티티가 기존 데이터베이스의 엔티티와 동일한지 판단하세요.

## 새로 추출된 엔티티
- 텍스트: {context.text}
- 유형: {context.entity_type}
- 문맥: {context.surrounding_text[:500]}
- 추론된 시대: {context.implied_year_start} ~ {context.implied_year_end}
- 관련 역할: {context.roles}

## 기존 후보들
{self._format_candidates(candidates)}

## 판단 기준
1. 이름이 비슷해도 시대가 다르면 다른 엔티티
2. 세대 구분 (I, II, XIV 등)이 다르면 반드시 다른 엔티티
3. 동명이인 가능성 항상 고려
4. 확실하지 않으면 PENDING 선택

## 응답 형식 (JSON)
{{
    "decision": "CREATE_NEW" | "LINK_EXISTING" | "PENDING",
    "linked_entity_id": null | 기존엔티티ID,
    "confidence": 0.0 ~ 1.0,
    "reasoning": "판단 이유 설명"
}}
"""
```

### 4.2 검증 레이어

Archivist 결정 후 추가 검증:

```python
class ArchivistValidator:
    """Archivist 결정의 2차 검증"""

    VALIDATION_RULES = [
        # 규칙 1: 세대 구분 충돌 시 병합 금지
        ("ordinal_conflict", lambda d:
            d.decision != "LINK_EXISTING" or
            not check_ordinal_conflict(d.new_text, d.linked_name)
        ),

        # 규칙 2: 200년 이상 시간차 병합 경고
        ("time_gap", lambda d:
            d.decision != "LINK_EXISTING" or
            abs(d.new_year - d.linked_year) < 200
        ),

        # 규칙 3: 다른 타입 병합 금지
        ("type_mismatch", lambda d:
            d.decision != "LINK_EXISTING" or
            d.new_type == d.linked_type
        ),
    ]

    def validate(self, decision: ArchivistDecision) -> ValidationResult:
        failures = []
        for rule_name, rule_fn in self.VALIDATION_RULES:
            if not rule_fn(decision):
                failures.append(rule_name)

        if failures:
            return ValidationResult(
                valid=False,
                override_decision="PENDING",
                failures=failures,
                message=f"검증 실패: {failures}. 사람 검토 필요."
            )

        return ValidationResult(valid=True)
```

---

## 5. 보류(Pending) 처리 시스템

### 5.1 Pending Queue

```sql
CREATE TABLE pending_entity_decisions (
    id SERIAL PRIMARY KEY,

    -- 새 엔티티 정보
    extracted_text VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    context_text TEXT,
    source_id INTEGER REFERENCES text_sources(id),

    -- Archivist 판단
    archivist_decision VARCHAR(20),
    archivist_confidence DECIMAL(3,2),
    archivist_reasoning TEXT,
    candidate_entity_id INTEGER,  -- LINK_EXISTING 후보

    -- 검증 결과
    validation_failures TEXT[],

    -- 상태
    status VARCHAR(20) DEFAULT 'pending',  -- pending, resolved, rejected
    resolved_decision VARCHAR(20),  -- 최종 결정
    resolved_entity_id INTEGER,
    resolved_by INTEGER REFERENCES masters(id),
    resolved_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 관리자 인터페이스 (추후 구현)

```
┌────────────────────────────────────────────────────────────────┐
│ Pending Entity Decisions                              [Filter] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ #142 "Louis XV" (Person)                      Confidence: 72%  │
│ ├─ Context: "...Louis XV continued the policies of..."        │
│ ├─ Candidate: Louis XIV (ID: 234)                             │
│ ├─ Archivist says: LINK_EXISTING                              │
│ ├─ Validation: ❌ ordinal_conflict (XIV ≠ XV)                 │
│ │                                                              │
│ └─ Actions: [Create New] [Link to #234] [Search Others]       │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ #143 "Plato" (Person)                         Confidence: 65%  │
│ ├─ Context: "...Plato wrote comedies in Athens..."            │
│ ├─ Candidate: Plato (ID: 12) - Philosopher                    │
│ ├─ Archivist says: PENDING                                    │
│ ├─ Note: 희극작가 Plato ≠ 철학자 Plato 가능성                   │
│ │                                                              │
│ └─ Actions: [Create New] [Link to #12] [Search Others]        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. 신뢰도 보장 메커니즘

### 6.1 다단계 검증

```
Level 1: NER 추출
    ↓ (신뢰도 점수 포함)
Level 2: Archivist 판단
    ↓ (LLM 기반 문맥 분석)
Level 3: 규칙 기반 검증
    ↓ (하드 규칙으로 명백한 오류 차단)
Level 4: Pending Queue
    ↓ (불확실한 케이스 사람 검토)
Level 5: 저장소 반영
```

### 6.2 감사 로그 (Audit Trail)

```sql
CREATE TABLE entity_decision_log (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER,
    entity_type VARCHAR(50),

    -- 결정 정보
    decision_type VARCHAR(20),  -- created, linked, merged, rejected
    decision_source VARCHAR(20),  -- archivist, validator, human

    -- 상세
    confidence DECIMAL(3,2),
    reasoning TEXT,
    linked_from_id INTEGER,  -- 병합된 경우 원본

    -- 메타
    source_text_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 6.3 통계 및 모니터링

```python
class ArchivistMetrics:
    """Archivist 성능 모니터링"""

    async def get_stats(self, period_days: int = 30) -> dict:
        return {
            "total_decisions": await count_decisions(period_days),
            "by_type": {
                "CREATE_NEW": await count_by_type("CREATE_NEW", period_days),
                "LINK_EXISTING": await count_by_type("LINK_EXISTING", period_days),
                "PENDING": await count_by_type("PENDING", period_days),
            },
            "pending_queue_size": await count_pending(),
            "validation_failure_rate": await calc_failure_rate(period_days),
            "human_override_rate": await calc_override_rate(period_days),
            "avg_confidence": await calc_avg_confidence(period_days),
        }
```

---

## 7. 실제 처리 예시

### 예시 1: Louis XIV vs Louis XV

```
입력: "Louis XV, grandson of Louis XIV, became king in 1715..."

1. NER 추출:
   - "Louis XV" → Person
   - "Louis XIV" → Person
   - "1715" → Time

2. Archivist 처리 (Louis XV):
   - 후보 검색: Louis XIV (ID: 234) 발견
   - 이름 유사도: 0.89
   - 시간 분석: 1715 시작 vs Louis XIV 1715 사망
   - 세대 구분: XV ≠ XIV → 충돌!

3. 결정:
   decision: CREATE_NEW
   confidence: 0.95
   reasoning: "세대 구분자가 명확히 다름 (XV vs XIV).
              문맥상 손자 관계로 별개 인물 확실."

4. 결과:
   - Louis XV → 새 Person 엔티티 생성 (ID: 456)
   - person_relationships 추가: 456 → 234 (grandson)
```

### 예시 2: 동명이인 Plato

```
입력: "Plato, the comic poet, mocked Hyperbolus in his plays..."

1. NER 추출:
   - "Plato" → Person
   - "Hyperbolus" → Person

2. Archivist 처리 (Plato):
   - 후보 검색: Plato 철학자 (ID: 12) 발견
   - 이름 유사도: 1.0 (정확 일치)
   - 문맥 분석: "comic poet", "plays" → 희극작가
   - 기존 Plato: "philosopher", "dialogues" → 철학자
   - 역할 불일치!

3. 결정:
   decision: CREATE_NEW
   confidence: 0.88
   reasoning: "문맥상 희극작가로 언급됨.
              기존 Plato(ID:12)는 철학자로, 역할이 완전히 다름.
              고대 그리스에 동명의 희극작가 존재 확인됨."

4. 결과:
   - Plato (희극작가) → 새 Person 엔티티 생성 (ID: 789)
   - 역할: comic_poet
   - 구분용 별칭 추가: "Plato Comicus"
```

---

## 8. 구현 우선순위

### Phase 1: 기본 인프라
- [ ] EntityContext 데이터 구조
- [ ] 후보 검색 (이름 + 벡터 + 시간)
- [ ] 기본 점수 체계

### Phase 2: Archivist Core
- [ ] LLM 기반 판단 로직
- [ ] 세대 구분 특수 처리
- [ ] 검증 레이어

### Phase 3: Pending 시스템
- [ ] pending_entity_decisions 테이블
- [ ] 기본 관리 API
- [ ] 감사 로그

### Phase 4: 모니터링
- [ ] 통계 대시보드
- [ ] 알림 시스템
- [ ] 성능 튜닝

---

## 9. 핵심 보장

| 보장 사항 | 구현 방법 |
|----------|----------|
| **세대 구분 절대 병합 금지** | 하드코딩된 규칙으로 차단 |
| **불확실하면 사람 검토** | Pending Queue로 이관 |
| **모든 결정 추적 가능** | Audit Log 기록 |
| **오판 시 복구 가능** | 결정 이력 보존, 롤백 지원 |

> **결론**: 규칙 기반 자동 처리의 위험을 인식하고, 문맥 기반 LLM 판단 + 하드 규칙 검증 + 사람 검토 3단계로 신뢰할 수 있는 저장고를 구축합니다.
