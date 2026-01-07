# Batch API Token Issue - 2026-01-06

## 문제 요약

**$50 손실**: OpenAI Batch API로 76,008개 문서를 처리했으나 **99.33%가 빈 결과** 반환.

## 근본 원인

### gpt-5-nano의 reasoning tokens 문제

```
설정: max_completion_tokens: 3000
실제 사용:
  - reasoning_tokens: 3000 (내부 추론에 전부 소진)
  - content: "" (빈 문자열)
  - finish_reason: "length" (토큰 제한 도달)
```

gpt-5-nano는 응답 생성 전에 **내부 추론(reasoning)**을 수행하며, 이 토큰도 `max_completion_tokens` 제한에 포함됨.

### 결과

| 항목 | 값 |
|-----|---|
| 총 문서 | 76,008 |
| 성공 (content 있음) | 511 (0.67%) |
| 실패 (content 없음) | 75,497 (99.33%) |
| 실패 원인 | `finish_reason: "length"` |
| 비용 | ~$22.80 (낭비) |

## 해결 방법

### 옵션 1: max_completion_tokens 제거 (권장)

```python
# Before (실패)
"max_completion_tokens": 3000

# After (성공)
# max_completion_tokens 파라미터 생략
```

테스트 결과 (max_completion_tokens 없이):
- reasoning_tokens: 384
- completion_tokens: 412
- content: 정상 JSON 출력

### 옵션 2: 매우 높은 값 설정

```python
"max_completion_tokens": 999999
```

## 수정 사항

### `batch_processor.py`

```python
def create_batch_request(doc_id: str, text: str) -> dict:
    return {
        "custom_id": doc_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-5-nano",
            "messages": [...],
            "response_format": {...}
            # max_completion_tokens 제거
        }
    }
```

## 재처리 계획

1. 기존 배치 결과 삭제
2. max_completion_tokens 없이 배치 파일 재생성
3. 순차적으로 배치 제출 (토큰 한도 40M 고려)
4. 예상 비용: ~$30-50 (reasoning 포함)

## 교훈

1. **gpt-5 시리즈는 reasoning tokens을 사용함**
   - max_completion_tokens = reasoning + actual_output
   - 너무 낮으면 reasoning에 전부 소진

2. **Batch API 테스트 필수**
   - 대량 제출 전 10-100개로 테스트
   - content가 비어있는지 확인

3. **모델별 특성 파악**
   - gpt-4: max_tokens 사용
   - gpt-5: max_completion_tokens 사용 + reasoning

## 관련 파일

- `poc/scripts/integrated_ner/batch_processor.py`: 배치 생성 스크립트
- `poc/data/integrated_ner_full/batch_*_output.jsonl`: 실패한 결과 파일
- `docs/logs/BATCH_FAILURE_ANALYSIS_20260105.md`: 이전 실패 분석

## 비용 손실 내역

| 날짜 | 배치 | 비용 | 원인 |
|-----|-----|-----|-----|
| 2026-01-05 | 4개 | ~$10 | gpt-4o-mini 권한 없음 |
| 2026-01-06 | 8개 | ~$22.80 | max_completion_tokens 부족 |
| **총 손실** | | **~$32.80** | |
