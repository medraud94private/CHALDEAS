# Archivist V3 Changelog

## 2026-01-03 22:25: Critical Chunk Processing Fix

### 문제
- 파일의 첫 5000자만 처리하고 나머지 전부 버림
- 10만자 파일이면 95% 데이터 손실

### 수정
```python
# Before (잘못됨)
entities = await self.ner.extract_entities(content[:chunk_size])

# After (전체 처리)
for chunk_start in range(0, len(content), chunk_size):
    chunk_end = min(chunk_start + chunk_size, len(content))
    chunk = content[chunk_start:chunk_end]
    entities = await self.ner.extract_entities(chunk)
```

### 데이터 구조 변경
```json
{
  "mentions": [{
    "source_path": "british_library/.../000037.json",
    "start": 9784,        // 엔티티 시작 (파일 기준 절대 위치)
    "end": 9790,          // 엔티티 끝
    "chunk_start": 9000,  // 이 청크 시작 ← 추가
    "chunk_end": 12000    // 이 청크 끝 ← 추가
  }]
}
```

### Curator 사용법
```python
# 청크 전체 가져오기
chunk = content[mention["chunk_start"]:mention["chunk_end"]]

# 청크 내 엔티티 상대 위치
entity_pos = mention["start"] - mention["chunk_start"]
```

---

## 2026-01-03: V3 Major Redesign

### 문제점 발견 및 수정

#### 1. 체크포인트 동기화 문제
- **문제**: `pending_queue.append()`는 즉시 파일에 쓰지만, checkpoint는 50파일마다 저장
- **결과**: 중간에 중단되면 재시작 시 엔티티 중복
- **해결**: `buffer_append()` + `flush_buffer()` 도입, checkpoint 저장 시 함께 flush

#### 2. 엔티티 중복 (Deduplication → Merging)
- **문제**: 같은 "Alexander"가 100개 파일에서 나오면 100개 pending item 생성
- **해결**: `EntityRegistry`로 엔티티 병합, 모든 mention 위치 추적
- **용어 정정**: "중복 제거"가 아니라 "병합"

#### 3. 소스 추적 불완전
- **문제**: 파일명만 저장 (`000037.json`) → 다른 폴더에 같은 이름 있으면 충돌
- **문제**: 원문 내 위치 (start, end) 저장 안 함 → Curator가 컨텍스트 다시 찾아야 함
- **해결**:
  - `source` → `source_path` (전체 상대 경로)
  - `mentions` 배열로 모든 언급 위치 저장
  - `start`, `end`, `chunk_index` 추가

#### 4. 컨텍스트 저장 문제
- **문제**: "가장 긴 컨텍스트가 최적"이라는 근거 없는 로직
- **문제**: 컨텍스트 선택은 Curator 단계 작업
- **해결**:
  - `context` → `sample` (이름 변경, 참조용임을 명확히)
  - 실제 컨텍스트는 Curator가 `source_path` + `start`/`end`로 원문에서 추출

#### 5. Phase 2 candidates 문제
- **문제**: Phase 1 registry에서 candidates 찾음 → 자기 자신 찾아서 LINK
- **해결**: Phase 2는 자체 `decided_entities`에서만 candidates 찾음

#### 6. 메모리 효율성
- **문제**: `get_unprocessed()`가 전체 pending_queue 메모리에 로드
- **해결**: `iter_unprocessed()` 스트리밍 generator 추가

#### 7. 파일 카운트 느림
- **문제**: 76,000개 파일 카운트에 10초 이상
- **해결**: `FileCountCache`로 캐싱

---

### 변경된 데이터 구조

#### EntityRegistry Entity
```json
{
    "key": "person:alexander the great",
    "text": "Alexander the Great",
    "normalized": "alexander the great",
    "entity_type": "person",
    "sample_text": "Alexander the Great",
    "mentions": [
        {
            "source_path": "british_library/extracted/000037.json",
            "start": 1234,
            "end": 1254,
            "chunk_index": 0
        }
    ],
    "mention_count": 1,
    "first_seen": "2026-01-03T12:00:00"
}
```

#### Pending Queue Item
```json
{
    "id": 1,
    "text": "Alexander the Great",
    "entity_type": "person",
    "entity_key": "person:alexander the great",
    "mentions": [
        {
            "source_path": "british_library/extracted/000037.json",
            "start": 1234,
            "end": 1254,
            "chunk_index": 0
        }
    ],
    "mention_count": 1,
    "sample": "Alexander the Great",
    "created_at": "2026-01-03T12:00:00"
}
```

#### Phase 1 Checkpoint (V3)
```json
{
    "version": 3,
    "timestamp": "2026-01-03T12:00:00",
    "processed_files_count": 100,
    "processed_files": ["british_library/extracted/000037.json", ...],
    "exported_entities": ["person:alexander", "location:rome", ...],
    "registry": {
        "entities": [...],
        "unique_count": 500,
        "total_mentions": 1500
    },
    "pending_flushed": 50
}
```

---

### 변경된 파일 목록

| 파일 | 변경 내용 |
|------|-----------|
| `poc/app/core/checkpoint.py` | EntityRegistry 재설계, Mention dataclass, buffer 시스템, atomic write |
| `poc/scripts/archivist_fullscale_v3.py` | 위치 추적, export 로직, 새 API 사용 |
| `poc/scripts/archivist_phase2_v3.py` | decided_entities 기반 candidates, 새 구조 대응 |
| `poc/scripts/run_archivist_full.py` | V3 스크립트 사용하도록 변경 |
| `poc/docs/ARCHIVIST_V3_DESIGN.md` | 설계 문서 |

---

### API 변경

#### EntityRegistry
```python
# Before
registry.add_or_update(text, entity_type, context, source)

# After
registry.add_mention(text, entity_type, source_path, start, end, chunk_index)
```

#### PendingQueue
```python
# Before
pending_queue.buffer_append(text, entity_type, context, entity_key, source)

# After
pending_queue.buffer_append(text, entity_type, entity_key, mentions, sample)
```

---

### Curator 통합

```python
def get_original_context(mention: dict, context_size: int = 200) -> str:
    """원본 파일에서 정확한 컨텍스트 추출"""
    filepath = DATA_DIR / mention["source_path"]

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start = max(0, mention["start"] - context_size)
    end = min(len(content), mention["end"] + context_size)

    return content[start:end]

# 사용 예
entity = registry.get_entity("person:alexander the great")
for mention in entity["mentions"]:
    context = get_original_context(mention)
    print(f"Source: {mention['source_path']}")
    print(f"Position: {mention['start']}-{mention['end']}")
    print(f"Context: {context}")
```

---

### 테스트 결과

```
Phase 1 (10 files):
- Raw entities: 346
- Unique entities: 283
- Merge ratio: 18.2% reduced
- Speed: 2,159 files/hour

Phase 2 (5 items):
- CREATE_NEW: 5
- LINK_EXISTING: 0
- Working correctly with new structure
```

---

### 예상 개선 효과

| 항목 | Before | After |
|------|--------|-------|
| Raw entities | ~3,000,000 | ~3,000,000 |
| Unique entities | ~3,000,000 (중복 포함) | ~200,000~500,000 (병합 후) |
| Phase 2 예상 시간 | 69일 | 5~15일 |
| 소스 추적 | 파일명만 | 전체 경로 + 위치 |
| Curator 통합 | 불가능 | 가능 |
