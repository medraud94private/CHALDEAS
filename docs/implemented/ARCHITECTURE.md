# CHALDEAS System Architecture

## 구현 상태: 완료

## 1. World-Centric Architecture

CHALDEAS는 **World-Centric Architecture** 패러다임을 따릅니다.

### 핵심 원칙

1. **World는 명시적이고 불변** - 상태는 항상 추적 가능
2. **Intelligence는 제안만 하고 실행하지 않음** - 방화벽 원칙
3. **모든 값은 "왜?"에 답할 수 있음** - 완전한 설명 가능성
4. **시스템 안정성은 모델 크기와 무관** - 결정론적 런타임

### 시스템 흐름

```
User Query
    │
    ▼
┌─────────────────┐
│   CHALDEAS      │ ← World State (Immutable Snapshot)
│   Layer 1-2     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     SHEBA       │ ← Observation (Query Understanding)
│   Layer 3       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     LOGOS       │ ← Proposal (LLM Response)
│   (Actor)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PAPERMOON     │ ← Verification (Fact Check)
│   (Authority)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    LAPLACE      │ ← Explanation (Source Attribution)
│   Layer 7       │
└────────┬────────┘
         │
         ▼
     Response
```

## 2. 7-Layer Core

```
Layer 7: EXPLAIN (LAPLACE)     - 구조적 해석, 인과관계 추적
Layer 6: PATCH / APPLY         - 상태 변경의 유일한 경로
Layer 5: EFFECT RUNTIME        - 부수효과 없는 순수 함수
Layer 4: ACTION (Availability) - 행동 가용성 계산
Layer 3: PROJECTION (SHEBA)    - 읽기 전용 뷰 생성
Layer 2: SNAPSHOT              - 불변 상태 스냅샷
Layer 1: SCHEMA                - 세계 구조 정의
```

## 3. 폴더 구조

```
backend/app/
├── core/
│   ├── chaldeas/      # Layer 1-2: 세계 상태
│   ├── sheba/         # Layer 3: 관측
│   ├── laplace/       # Layer 7: 설명
│   ├── trismegistus/  # Orchestrator
│   ├── papermoon/     # Authority
│   ├── logos/         # Actor (LLM)
│   └── anima/         # Teacher (Future)
│
├── api/               # REST API
├── models/            # DB Models
├── schemas/           # Pydantic
└── services/          # Business Logic
```

## 4. 구현된 파일들

| 파일 | 역할 |
|------|------|
| `core/trismegistus/orchestrator.py` | 전체 파이프라인 조율 |
| `core/sheba/observer.py` | 질의 해석 및 컨텍스트 추출 |
| `core/logos/actor.py` | LLM 기반 응답 제안 |
| `core/papermoon/authority.py` | 제안 검증 |
| `core/laplace/explain.py` | 출처 연결 및 설명 |
