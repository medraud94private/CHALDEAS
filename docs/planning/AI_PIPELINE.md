# AI Pipeline 상세 기획

## 상태: 기획 중

## 1. 현재 구현된 파이프라인

```
Query → SHEBA → LOGOS → PAPERMOON → LAPLACE → Response
```

## 2. 향후 확장 계획

### 2.1 ANIMA (Teacher) 시스템

실패를 관찰하고 학습하는 시스템.

```python
class AnimaTeacher:
    def observe_failure(self, proposal, verification):
        """실패한 제안 관찰"""
        # 왜 실패했는지 분석
        # 패턴 기록
        pass

    def suggest_improvement(self, actor_type):
        """개선 제안"""
        # 프롬프트 개선
        # 컨텍스트 선택 개선
        pass
```

### 2.2 Multi-Actor 지원

여러 LLM을 동시에 사용하여 합의 도출.

```
Query → SHEBA → [LOGOS-Claude, LOGOS-GPT, LOGOS-Local]
                              ↓
                     PAPERMOON (합의 검증)
                              ↓
                          LAPLACE
```

### 2.3 Fork/Branch 시스템

World-Centric의 분기 탐색 구현.

```python
class Fork:
    parent_snapshot: Snapshot
    changes: list[Patch]
    status: "exploring" | "merged" | "abandoned"
```

---

## 3. 프롬프트 전략

### 3.1 SHEBA 관측 프롬프트
```
당신은 역사 질의를 분석하는 관측자입니다.
다음 질의에서 시간, 장소, 인물, 사건 정보를 추출하세요.

질의: {query}

JSON 형식으로 응답:
{
  "time": {"year": -490, "era": "BCE"},
  "location": {"name": "Marathon"},
  "persons": ["Miltiades"],
  "events": ["Battle of Marathon"]
}
```

### 3.2 LOGOS 응답 프롬프트
```
당신은 역사 전문가입니다.
다음 컨텍스트를 바탕으로 질문에 답하세요.

컨텍스트:
{context}

질문: {query}

규칙:
- 컨텍스트에 없는 정보는 추측하지 마세요
- 불확실한 경우 명시하세요
- 출처를 언급하세요
```

---

## 4. 외부 LLM 연동

### 4.1 지원 모델

| 제공자 | 모델 | 용도 |
|--------|------|------|
| Anthropic | Claude 3 Haiku | 빠른 응답 (기본) |
| Anthropic | Claude 3 Sonnet | 복잡한 질의 |
| OpenAI | GPT-3.5 Turbo | 대안 |
| Local | Llama 3 | 오프라인 지원 |

### 4.2 Fallback 전략

1. 1차: 설정된 기본 모델
2. 2차: 대안 모델
3. 3차: 로컬 모델
4. 4차: 컨텍스트만으로 응답 (LLM 없음)

---

## 5. 성능 최적화

### 5.1 캐싱

```python
# 동일 질의 캐시
cache_key = hash(query + str(context))
if cached := get_cache(cache_key):
    return cached
```

### 5.2 배치 처리

여러 관측을 한 번에 처리.

```python
async def batch_observe(queries: list[str]):
    observations = await asyncio.gather(*[
        sheba.observe(q) for q in queries
    ])
    return observations
```

---

## 6. 모니터링

### 6.1 메트릭

- 응답 시간 (p50, p95, p99)
- 검증 통과율
- 출처 연결률
- 사용자 피드백

### 6.2 로깅

```sql
-- proposal_logs 테이블
CREATE TABLE proposal_logs (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(50),
    action_type VARCHAR(100),
    proposal JSONB,
    decision VARCHAR(20),
    rationale TEXT,
    response_time_ms INTEGER,
    created_at TIMESTAMPTZ
);
```
