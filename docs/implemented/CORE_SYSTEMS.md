# Core Systems (FGO-Inspired)

## 구현 상태: 완료

CHALDEAS의 핵심 시스템들은 Fate/Grand Order의 칼데아 시스템에서
영감을 받아 명명되었습니다.

---

## CHALDEAS (칼데아스)
**지구 시뮬레이터 - World State**

FGO에서 인류의 미래를 관측하는 지구 모형처럼,
이 시스템은 전체 세계 상태를 관리합니다.

### 역할
- 불변 스냅샷 관리
- 스키마 정의 (Event, Person, Location)
- 상태 변경은 오직 Patch/Apply를 통해서만

### 구현
```
backend/app/core/chaldeas/
├── schema.py      # Layer 1
├── snapshot.py    # Layer 2
├── projection.py  # Layer 3
├── action.py      # Layer 4
├── effect.py      # Layer 5
└── patch.py       # Layer 6
```

---

## SHEBA (시바)
**근미래관측렌즈 - Observer**

FGO에서 특이점을 관측하는 렌즈처럼,
사용자 질의를 분석하고 관련 정보를 "관측"합니다.

### 역할
- 질의에서 시간/공간 컨텍스트 추출
- 관련 이벤트/인물/장소 식별
- 구조화된 관측 결과 제공

### 구현
```python
# backend/app/core/sheba/observer.py

class ShebaObserver:
    async def observe(self, query, context) -> Observation:
        # 시간 추출: "490 BCE" → year=-490
        # 장소 추출: "Marathon" → location_id=10
        # 관련 엔티티 검색
        return Observation(...)
```

---

## LAPLACE (라플라스)
**사상기록전자해 - Explainer**

피에르-시몽 라플라스의 결정론적 우주관에서 이름을 따,
모든 값의 출처와 인과관계를 추적합니다.

### 역할
- 출처 연결 (Perseus, CText 등)
- 인과관계 추적
- "왜?" 질문에 답변

### 구현
```python
# backend/app/core/laplace/explain.py

class LaplaceExplainer:
    async def explain(self, proposal, observation) -> Explanation:
        sources = await self._find_sources(observation)
        causality = await self._trace_causality(observation)
        return Explanation(sources, causality, suggestions)
```

---

## TRISMEGISTUS (트리스메기스투스)
**삼중 위대한 자 - Orchestrator**

헤르메스 트리스메기스투스처럼 신비로운 지혜를 조율하는
이 시스템은 모든 다른 시스템을 조율합니다.

### 역할
- 질의 수신
- SHEBA → LOGOS → PAPERMOON → LAPLACE 파이프라인 조율
- 최종 응답 구성

### 구현
```python
# backend/app/core/trismegistus/orchestrator.py

class Orchestrator:
    async def process_query(self, query, context) -> ChatResponse:
        observation = await self.sheba.observe(query, context)
        proposal = await self.logos.propose(query, observation)
        verification = await self.papermoon.verify(proposal)
        explanation = await self.laplace.explain(proposal, observation)
        return ChatResponse(...)
```

---

## PAPERMOON (페이퍼문)
**종이 달 - Authority**

취약하지만 필수적인 검증 시스템.
AI 제안을 실행 전에 검증합니다.

### 역할
- LOGOS 제안 검증
- 사실 정확성 체크
- 승인/거부/수정 요청 결정

### 구현
```python
# backend/app/core/papermoon/authority.py

class PapermoonAuthority:
    async def verify(self, proposal, observation) -> VerificationResult:
        # 날짜 일관성 체크
        # 엔티티 존재 확인
        # 신뢰도 계산
        return VerificationResult(approved, confidence, corrections)
```

---

## LOGOS (로고스)
**말씀/이성 - Actor**

그리스 철학의 로고스 개념처럼,
이성적 응답을 "제안"합니다 (실행은 하지 않음).

### 역할
- LLM을 통한 응답 생성
- 제안만 하고 실행은 하지 않음 (방화벽 원칙)
- 컨텍스트 기반 답변

### 구현
```python
# backend/app/core/logos/actor.py

class LogosActor:
    async def propose(self, query, observation) -> Proposal:
        # LLM으로 응답 생성
        # 반드시 제안만 - 직접 실행 불가
        return Proposal(answer, rationale, confidence)
```

---

## ANIMA (아니마)
**영혼 - Teacher**

**상태: 계획 중**

융의 아니마 개념처럼 무의식적 학습을 담당할 시스템.

### 계획된 역할
- 실패 관찰 및 패턴 학습
- LOGOS 개선 피드백
- 지식 증류
