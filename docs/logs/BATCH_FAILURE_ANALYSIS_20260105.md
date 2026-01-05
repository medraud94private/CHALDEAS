# Batch API Failure Analysis - 2026-01-05

## Summary

OpenAI Batch API를 사용한 대규모 NER 처리 중 99%의 요청이 실패하는 문제 발생. 원인 분석 및 수정 완료.

## Timeline

1. **배치 제출** (17:50경)
   - 63,985개 문서를 7개 chunk로 분할 (각 10,000개)
   - 4개 chunk만 업로드 완료 후 VSCode 크래시

2. **문제 발견**
   - chunk_000, 001: `in_progress`이나 ~99% 실패
   - chunk_002, 003: `token_limit_exceeded`로 즉시 실패
   - chunk_004~006: 업로드 전 크래시

## Root Cause Analysis

### 문제 1: 잘못된 모델 사용

```
Error: "Project does not have access to model `gpt-4o-mini-2024-07-18-batch`"
```

**원인**: `batch_processor.py`에서 `gpt-4o-mini`를 하드코딩
- 일반 API에서는 작동하나 Batch API에서는 권한 없음
- CLAUDE.md에 명시된 `gpt-5-nano`를 사용해야 함

**수정**:
```python
# Before
"model": "gpt-4o-mini"

# After
"model": "gpt-5-nano"
```

### 문제 2: 잘못된 파라미터

```
Error: "Unsupported parameter: 'max_tokens' is not supported with this model"
```

**원인**: GPT-5 시리즈는 `max_tokens` 대신 `max_completion_tokens` 사용

**수정**:
```python
# Before
"max_tokens": 3000

# After
"max_completion_tokens": 3000
```

### 문제 3: 토큰 한도 초과

```
Error: "Enqueued token limit reached for gpt-4o-mini. Limit: 40,000,000"
```

**원인**: 4개 배치를 동시에 제출하여 대기열 토큰 한도 초과

**해결책**: 순차적으로 배치 제출 또는 완료 후 다음 배치 제출

## Files Modified

### `poc/scripts/integrated_ner/batch_processor.py`
- Line 173: `gpt-4o-mini` → `gpt-5-nano`
- Line 186: `max_tokens` → `max_completion_tokens`

### `poc/scripts/integrated_ner/extractor.py`
- Lines 30-34: 모델 폴백 순서 및 가격 정보 수정

```python
# 모델 폴백 순서 (Batch API 가격 기준, per 1M tokens)
MODELS = [
    ("gpt-5-nano", 0.05, 0.40),           # 기본: $0.05 input, $0.40 output
    ("gpt-5-mini", 0.25, 2.00),           # 폴백 1: $0.25 input, $2.00 output
    ("gpt-5.1-chat-latest", 1.25, 10.00), # 폴백 2: $1.25 input, $10.00 output
]
```

## Verification

gpt-5-nano로 5개 요청 테스트 배치 실행:
- **결과**: 5/5 성공 (100%)
- **Batch ID**: `batch_695b8601a5d481909a189d6a9c59c50a`

## Additional Fix: TXT File Support

### 문제 4: Gutenberg 문서 누락

**원인**: `batch_processor.py`가 `*_text.json`만 처리
- British Library: JSON 형식 (63,985개)
- Gutenberg: TXT 형식 (12,031개) - **누락됨**

**수정**:
```python
# Before
for doc_path in subdir.glob("*_text.json"):

# After (JSON + TXT, 재귀 검색)
for doc_path in subdir.rglob("*_text.json"):
    doc_paths.append(doc_path)
for doc_path in subdir.rglob("*.txt"):
    doc_paths.append(doc_path)
```

`load_document()` 함수도 TXT 지원 추가:
```python
def load_document(doc_path: Path) -> str:
    with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
        if doc_path.suffix == '.txt':
            return f.read()
        else:
            data = json.load(f)
            # ... JSON 처리
```

## Target Documents

| 소스 | 형식 | 개수 |
|------|------|------|
| British Library | JSON | 63,985 |
| Gutenberg | TXT | 12,031 |
| Arthurian | TXT | 10 |
| **총합** | | **76,026** |

## Next Steps

1. 기존 잘못된 chunk 파일 삭제
2. `gpt-5-nano` + `max_completion_tokens`로 배치 파일 재생성
3. 토큰 한도 고려하여 순차적으로 배치 제출

## Cost Estimation (gpt-5-nano Batch API)

| Item | Value |
|------|-------|
| Documents | 76,026 |
| Avg input tokens | ~2,000 |
| Avg output tokens | ~500 |
| Total input | ~152M tokens |
| Total output | ~38M tokens |
| Input cost | $7.60 |
| Output cost | $15.20 |
| **Total** | **~$22.80** |

## Lessons Learned

1. CLAUDE.md에 명시된 모델 사용 철저히 확인
2. GPT-5 시리즈는 파라미터 이름이 다름 (`max_completion_tokens`)
3. Batch API 토큰 한도(40M) 고려하여 순차 제출 필요
4. 배치 제출 전 소규모 테스트 필수
5. 다양한 데이터 소스 형식 확인 (JSON, TXT 등)
6. 중첩 폴더 구조 고려하여 `rglob` 사용
