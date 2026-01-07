# Batch NER 실패 분석 (2026-01-06)

## 요약

**76,019건 배치 처리 완료했으나 결과물 전부 무효 (0% 유효)**

## 원인

`max_completion_tokens: 3000` 제한으로 인해 gpt-5-nano의 reasoning 토큰이 전체 한도를 소진하여 실제 output이 생성되지 않음.

## 토큰 사용 분석

| 항목 | 값 |
|------|-----|
| prompt_tokens | ~1,900 |
| completion_tokens | 3,000 (한도 도달) |
| reasoning_tokens | 3,000 (100% 소진) |
| **actual output** | **0** |
| finish_reason | `length` (잘림) |

## 문제의 배치 요청 설정

```json
{
  "model": "gpt-5-nano",
  "max_completion_tokens": 3000,  // <-- 문제!
  "response_format": {
    "type": "json_schema",
    "json_schema": { ... }
  }
}
```

## gpt-5-nano 특성

- **Reasoning model**: 응답 전 내부 reasoning 과정 수행
- `max_completion_tokens`는 reasoning + output 합산 한도
- 3000 토큰 제한 시 reasoning이 전부 소진 → output 0

## 해결 방안

`max_completion_tokens` 제거 또는 매우 큰 값 설정:

```json
{
  "model": "gpt-5-nano",
  // max_completion_tokens 생략 (무제한)
  "response_format": { ... }
}
```

## 재처리 필요

| 항목 | 수량 |
|------|------|
| 총 문서 | 76,019 |
| 유효 결과 | 0 |
| 재처리 필요 | 76,019 (100%) |

## 비용 손실

- 이번 배치 비용: ~$15-20 (추정, 50% 할인 적용)
- 재처리 예상 비용: ~$30-40 (reasoning 토큰 증가로 더 높을 수 있음)

## 교훈

1. **Reasoning model 사용 시 토큰 한도 주의**: reasoning_tokens가 completion_tokens에 포함됨
2. **테스트 배치 먼저**: 소규모(10-100건) 테스트로 output 확인 후 대규모 진행
3. **finish_reason 모니터링**: `length`가 많으면 즉시 중단 필요

## 다음 단계

1. [ ] 배치 요청 파일 재생성 (max_completion_tokens 제거)
2. [ ] 소규모 테스트 (100건) 먼저 실행
3. [ ] 결과 확인 후 전체 재처리

---

*작성: 2026-01-06*
