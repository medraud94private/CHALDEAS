# Agentic RAG for Dummies 독후감

> **출처**: https://github.com/GiovanniPasq/agentic-rag-for-dummies
> **리뷰 일자**: 2026-01-07
> **관련성**: CHALDEAS V1 SHEBA 쿼리 파이프라인 개선

---

## 프로젝트 개요

LangGraph를 활용한 프로덕션 수준의 Agentic RAG 시스템 구축 튜토리얼. 기본 RAG를 넘어 실무에 필요한 고급 패턴들을 다룬다.

---

## 핵심 기능 분석

### 1. 계층적 인덱싱 (Hierarchical Indexing)

```
Parent Chunks: 마크다운 헤더 기반 대규모 섹션
     ↓
Child Chunks: 검색 정확도용 소규모 고정 크기 조각
```

**장점**: 정확도(child)와 맥락(parent)의 균형 제공

**CHALDEAS 적용 가능성**:
- 시대/지역별 대분류 → Parent
- 개별 사건/인물 → Child
- Historical Chain 생성 시 맥락 유지에 유용

### 2. 대화 메모리 & 쿼리 재작성

- 여러 질문 간 대화 맥락 유지
- 모호한 쿼리 자동 재작성 또는 명확화 요청

**CHALDEAS 적용 가능성**:
- SHEBA 쿼리 전처리 단계에 도입
- "그 사람의 다른 업적은?" → "알렉산더 대왕의 다른 업적은?"

### 3. Map-Reduce 병렬 처리

```
복잡한 질문
     ↓ 분할
[하위질문1] [하위질문2] [하위질문3]  ← 병렬 검색
     ↓ 통합
최종 응답
```

**CHALDEAS 적용 가능성**:
- Causal Chain 생성 시 다중 사건 동시 검색
- "로마 멸망의 원인들" → 경제/군사/정치 요인 병렬 탐색

### 4. 자체 수정 메커니즘 (Self-Correction)

```
검색 → 관련성 평가 → (불충분) → 쿼리 재작성 → 재검색
                   → (충분) → 응답 생성
```

**CHALDEAS 적용 가능성**:
- SHEBA 검색 결과 품질 자동 검증
- 신뢰도 낮은 결과 시 자동 재쿼리

---

## 기술 스택

| 구분 | 사용 기술 | 비고 |
|------|----------|------|
| LLM | Ollama, Gemini, OpenAI, Claude | 교체 가능 설계 |
| Vector DB | Qdrant | 하이브리드 검색 지원 |
| Embedding | HuggingFace (dense) + BM25 (sparse) | 의미 + 키워드 |
| 문서처리 | PyMuPDF → 마크다운 변환 | 계층 구조 보존 |
| 프레임워크 | LangGraph | 에이전트 워크플로우 |

---

## CHALDEAS 적용 제안

### 현재 파이프라인

```
User Query → SHEBA (단순 벡터 검색) → LOGOS → Response
```

### 개선안

```
User Query
     ↓
Query Rewriter (맥락 반영, 모호성 해소)
     ↓
Hierarchical Search
├── Parent: 시대/지역 맥락 검색
└── Child: 정밀 사건/인물 검색
     ↓
Relevance Checker
├── (불충분) → 쿼리 재작성 → 재검색
└── (충분) → 결과 전달
     ↓
LOGOS (응답 생성)
     ↓
PAPERMOON (검증)
     ↓
Response
```

### 우선순위 도입 항목

| 순위 | 기능 | 난이도 | 효과 |
|------|------|--------|------|
| 1 | Self-Correction Loop | 중 | 높음 |
| 2 | Query Rewriting | 하 | 중 |
| 3 | Hierarchical Indexing | 상 | 높음 |
| 4 | Map-Reduce 병렬처리 | 중 | 중 |

---

## 총평

### 장점

- "for dummies" 제목답게 개념 설명이 친절
- 노트북과 모듈식 프로젝트 이중 구조로 학습 + 실무 모두 지원
- LLM 제공자, 벡터DB 등 교체 가능한 모듈 설계

### 한계

- LangGraph 의존도 높음 (자체 아키텍처 있는 프로젝트엔 부분 차용 권장)
- 실제 프로덕션 운영 경험 기반 노하우는 부족

### 결론

CHALDEAS V1 개발 시 **SHEBA 쿼리 파이프라인 개선**에 참고할 가치 있음.
특히 **Hierarchical Indexing**과 **Self-Correction Loop**은 Historical Chain 품질 향상에 직접 기여 가능.

전체 프레임워크 도입보다는 **개념과 패턴만 차용**하여 기존 7-Layer 아키텍처에 통합하는 방식 권장.

---

## 참고 링크

- 원본 레포: https://github.com/GiovanniPasq/agentic-rag-for-dummies
- LangGraph 문서: https://langchain-ai.github.io/langgraph/
- Qdrant 문서: https://qdrant.tech/documentation/
