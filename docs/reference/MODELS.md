# CHALDEAS AI 모델 사용 현황

## 개요

CHALDEAS에서 사용하는 AI/LLM 모델들의 목록과 용도입니다.

---

## 1. 텍스트 생성 모델

### 1.1 OpenAI 모델

| 모델 | 용도 | 비용 | 비고 |
|-----|------|------|------|
| `gpt-5-nano` | NER 검증, 체인 생성 (기본) | ~$0.001/1K tokens | 빠르고 저렴 |
| `gpt-5.1-chat-latest` | 복잡한 체인, 품질 검증 (폴백) | ~$0.01/1K tokens | 고품질 |

### 1.2 사용 전략

```
일반 작업 → gpt-5-nano (90%)
    ↓ 품질 부족 시
고품질 작업 → gpt-5.1-chat-latest (10%)
```

---

## 2. NER (Named Entity Recognition) 모델

### 2.1 오픈소스 (1차)

| 모델 | 용도 | 비용 |
|-----|------|------|
| `spaCy en_core_web_lg` | 영어 NER | 무료 (로컬) |
| `spaCy zh_core_web_lg` | 중국어 NER | 무료 (로컬) |

### 2.2 LLM 검증 (2차)

| 모델 | 용도 | 비용 |
|-----|------|------|
| `gpt-5-nano` | 저신뢰도 엔티티 검증 | ~$0.001/1K tokens |

---

## 3. 임베딩 모델

| 모델 | 용도 | 차원 | 비용 |
|-----|------|------|------|
| `text-embedding-3-small` | 이벤트/인물 벡터 검색 | 1536 | ~$0.00002/1K tokens |

---

## 4. 모델 선택 기준

### 4.1 비용 최적화

```python
def select_model(task_complexity: str, budget_remaining: float) -> str:
    if budget_remaining < 0.1:  # $0.1 미만
        return "spacy_only"  # 무료

    if task_complexity == "simple":
        return "gpt-5-nano"
    elif task_complexity == "complex":
        return "gpt-5.1-chat-latest"
    else:
        return "gpt-5-nano"  # 기본값
```

### 4.2 품질 기준

| 작업 | 최소 품질 | 권장 모델 |
|-----|----------|----------|
| NER 추출 | 80% 정확도 | spaCy + gpt-5-nano |
| 체인 생성 | 90% 일관성 | gpt-5-nano |
| 시스템 체인 | 95% 품질 | gpt-5.1-chat-latest |

---

## 5. 환경 변수

```bash
# .env
OPENAI_API_KEY=sk-...

# 모델 설정
NER_PRIMARY_MODEL=gpt-5-nano
NER_FALLBACK_MODEL=gpt-5.1-chat-latest
CHAIN_PRIMARY_MODEL=gpt-5-nano
CHAIN_FALLBACK_MODEL=gpt-5.1-chat-latest
EMBEDDING_MODEL=text-embedding-3-small
```

---

## 6. 모델 성능 모니터링

### 6.1 메트릭

```python
class ModelMetrics:
    model_name: str
    call_count: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    error_rate: float
```

### 6.2 대시보드 예시

```
[Model Usage - Today]
gpt-5-nano:        142 calls, 45K tokens, $0.045, 320ms avg
gpt-5.1-chat-latest: 12 calls, 8K tokens, $0.08, 890ms avg
spaCy:             1,234 calls, 0 tokens, $0, 45ms avg
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-01 | 초기 문서 작성 |
