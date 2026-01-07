# Archivist V3 Design

## Overview

Archivist V3는 원본 파일에서 엔티티를 추출하고, 모든 언급(mention) 위치를 정확하게 추적합니다.

## Data Structures

### Entity (EntityRegistry)

```json
{
    "key": "person:alexander the great",
    "text": "Alexander the Great",
    "normalized": "alexander the great",
    "entity_type": "person",
    "sample_text": "Alexander the Great",
    "mentions": [
        {
            "source_path": "british_library/extracted/000037_01_text.json",
            "start": 1234,
            "end": 1254,
            "chunk_index": 0
        },
        {
            "source_path": "gutenberg/pg12345.txt",
            "start": 5678,
            "end": 5698,
            "chunk_index": 0
        }
    ],
    "mention_count": 2,
    "first_seen": "2026-01-03T12:00:00"
}
```

### Pending Queue Item

```json
{
    "id": 1,
    "text": "Alexander the Great",
    "entity_type": "person",
    "entity_key": "person:alexander the great",
    "mentions": [
        {
            "source_path": "british_library/extracted/000037_01_text.json",
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

### Phase 2 Decision

```json
{
    "pending_id": 1,
    "decision": "CREATE_NEW",
    "linked_entity_key": null,
    "confidence": 0.9,
    "processed_at": "2026-01-03T12:05:00"
}
```

## Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_path` | string | 전체 상대 경로 (예: `british_library/extracted/000037.json`) |
| `start` | int | 원문 내 시작 위치 (character offset) |
| `end` | int | 원문 내 끝 위치 (character offset) |
| `chunk_index` | int | 파일이 청크 분할된 경우, 몇 번째 청크인지 |
| `mentions` | array | 모든 언급 위치 목록 |
| `mention_count` | int | 총 언급 횟수 |
| `sample` | string | 참조용 샘플 텍스트 (preview) |

## Processing Flow

### Phase 1: NER Extraction + Entity Merging

```
1. 파일 읽기
2. spaCy NER로 엔티티 추출
3. 각 엔티티에 대해:
   - EntityRegistry.add_mention(text, type, source_path, start, end)
   - 이미 존재하면 mention만 추가
   - 새 엔티티면 새로 생성
4. Checkpoint 시:
   - 새 엔티티들을 pending_queue로 export
   - EntityRegistry + processed_files + exported_entities 저장
```

### Phase 2: LLM Decision

```
1. pending_queue에서 항목 읽기
2. decided_entities에서 유사 엔티티 찾기 (candidates)
3. candidates 있으면 LLM에게 판단 요청
4. 결과 저장:
   - LINK_EXISTING: 기존 엔티티에 연결
   - CREATE_NEW: 새 엔티티 생성, decided_entities에 추가
```

## Curator Integration

Curator가 원문 컨텍스트를 가져오는 방법:

```python
def get_context(mention: dict, context_size: int = 200) -> str:
    """원본 파일에서 컨텍스트 추출"""
    source_path = DATA_DIR / mention["source_path"]
    with open(source_path, 'r') as f:
        content = f.read()

    start = max(0, mention["start"] - context_size)
    end = min(len(content), mention["end"] + context_size)
    return content[start:end]

# 사용 예
entity = registry.get_entity("person:alexander the great")
for mention in entity["mentions"]:
    context = get_context(mention)
    print(f"From {mention['source_path']}:")
    print(context)
```

## Files

| File | Description |
|------|-------------|
| `pending_queue.jsonl` | Phase 1 → Phase 2 큐 (JSONL, append-only) |
| `phase1_checkpoint.json` | Phase 1 상태 저장 |
| `phase2_decisions.jsonl` | Phase 2 결정 기록 |
| `status.json` | 실시간 진행 상태 |

## Checkpoint Format (V3)

```json
{
    "version": 3,
    "timestamp": "2026-01-03T12:00:00",
    "processed_files_count": 100,
    "processed_files": ["path/to/file1.json", "path/to/file2.json"],
    "exported_entities": ["person:alexander", "location:rome"],
    "registry": {
        "entities": [...],
        "unique_count": 500,
        "total_mentions": 1500
    },
    "pending_flushed": 50
}
```
