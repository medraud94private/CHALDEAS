# Archivist PoC 오류 수정 보고서

**날짜**: 2026-01-02
**작업자**: Claude

---

## 1. 문제 요약

### 증상
- 이전 세션에서 실행된 테스트(`test_archivist.py --multiplier 10`)가 진행 중 오류 발생
- 거의 모든 엔티티가 `PENDING` 상태로 처리됨
- "Ollama error: " 및 "Qwen error: " 메시지 출력 (빈 에러 메시지)

### 로그 분석
```
[1/224] Processing: gutenberg/pg62507.txt
Ollama error:
Falling back to OpenAI...
Qwen error:
    PENDING: 'the Project Gutenberg License' (needs review)
```

---

## 2. 원인 분석

### 핵심 원인: Qwen3 Thinking Mode
Qwen3:8b 모델이 **thinking mode**를 사용하여 응답을 생성:

```json
{
  "response": "",           // 빈 응답!
  "thinking": "Okay, let's see...",  // thinking 모드 활성화
  "done_reason": "length"   // 토큰 제한에 걸림
}
```

### 기술적 문제
1. **API 엔드포인트 불일치**: `/api/generate`에서는 `think: false`가 작동하지 않음
2. **응답 필드**: `/api/generate`는 `response` 필드 사용, `/api/chat`은 `message.content` 사용
3. **토큰 제한**: `num_predict: 50`이 thinking 출력으로 소진됨

---

## 3. 해결 방안

### 3.1 API 엔드포인트 변경
```python
# Before
response = await client.post(
    f"{settings.ollama_base_url}/api/generate",
    ...
)

# After
response = await client.post(
    f"{settings.ollama_base_url}/api/chat",
    json={
        "messages": [{"role": "user", "content": prompt}],
        "think": False,  # Critical!
        ...
    }
)
```

### 3.2 응답 파싱 변경
```python
# Before
response_text = result.get("response", "")

# After
response_text = result.get("message", {}).get("content", "")
```

### 3.3 에러 핸들링 강화
- 재시도 횟수: 2회 -> 3회
- 타임아웃: 60초 -> 90초
- Exponential backoff 적용
- 연결 에러, 타임아웃 에러 구분 처리

---

## 4. 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `poc/app/core/archivist.py` | `/api/chat` 사용, `think: false` 추가, 에러 핸들링 강화 |
| `poc/app/core/extraction/ner_pipeline.py` | `/api/chat` 사용, `think: false` 추가, 에러 핸들링 강화 |
| `poc/run_archivist_3days.bat` | 3일 자동 실행용 배치 파일 생성 |

---

## 5. 테스트 결과

### 수정 전
```
PENDING: 100%+ (거의 모든 엔티티)
Qwen error 지속 발생
```

### 수정 후
```
Total Decisions: 436
- CREATE_NEW:    179 (41.1%)
- LINK_EXISTING: 257 (58.9%)
- PENDING:       0 (0.0%)  ← 완전 해결!

Average Confidence: 0.83
Exit Code: 0 (성공)
```

### Disambiguation Test
```
Accuracy: 83.3% (10/12)
- Louis XIV/XV 구분: OK
- Socrates 링킹: OK
- Henry VII/VIII 구분: OK
- Napoleon I/III 구분: OK
```

---

## 6. 사흘간 자동 실행 방법

### 실행 명령
```batch
cd C:\Projects\Chaldeas\poc
run_archivist_3days.bat
```

### 특징
- Ollama 상태 자동 확인
- 에러 발생 시 60초 대기 후 자동 재시작
- 로그 파일 자동 생성 (`logs/archivist_3day_YYYYMMDD_HHMM.log`)
- SAMPLE_MULTIPLIER=10 (약 340개 텍스트)

---

## 7. 참고 문서

- [Ollama Thinking Mode Documentation](https://docs.ollama.com/capabilities/thinking)
- [GitHub Issue: Disable Thinking Mode](https://github.com/ollama/ollama/issues/10456)

---

## 8. 결론

Qwen3 모델의 thinking mode가 `/api/generate`에서 제대로 비활성화되지 않는 문제를 `/api/chat` 엔드포인트 사용으로 해결했습니다. 추가로 에러 핸들링을 강화하여 안정적인 장기 실행이 가능해졌습니다.
