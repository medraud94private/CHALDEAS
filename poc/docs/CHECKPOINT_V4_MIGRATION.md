# Checkpoint V4 Migration

## 변경 일시
2026-01-04 09:30

## 문제점 (V3)
- `phase1_checkpoint.json`이 811MB+ 크기
- 모든 엔티티의 mentions (200만개)를 JSON에 포함
- 50개 파일마다 전체 811MB를 덮어쓰기 → 저장 시간 60초+
- 진행할수록 점점 느려짐

## 해결책 (V4)
mentions를 별도 JSONL 파일로 분리 (append-only)

### 파일 구조 변경

**V3 (이전)**:
```
phase1_checkpoint.json (824MB)
├── processed_files: [...]
└── registry.entities: [
      {
        "key": "person:alexander",
        "mentions": [...200만개...]  ← 문제!
      }
    ]
```

**V4 (현재)**:
```
phase1_checkpoint.json (310MB)   ← 경량화
├── processed_files: [...]
└── registry.entities: [
      {
        "key": "person:alexander",
        "mention_count": 1523       ← mentions 제거, count만
      }
    ]

mentions.jsonl (390MB, append-only)   ← 신규
├── {"entity_key": "person:alexander", "source_path": "...", "start": 100, ...}
└── ...
```

### 성능 개선

| 항목 | V3 | V4 |
|-----|----|----|
| checkpoint 저장 크기 | 824MB | 310MB |
| checkpoint 저장 방식 | 전체 덮어쓰기 | 전체 덮어쓰기 (작은 크기) |
| mentions 저장 방식 | checkpoint에 포함 | append-only (별도 파일) |
| 예상 저장 시간 | 60초+ | ~20초 |

## 코드 변경 사항

### 1. `checkpoint.py`
- `MentionStore` 클래스 추가
- `EntityRegistry`에서 mentions 저장 제거, MentionStore로 위임
- `Phase1Checkpoint.save()`에 mention_store 파라미터 추가

### 2. `archivist_fullscale_v3.py`
- MentionStore 인스턴스 생성 및 연결
- PendingQueue.buffer_append() 시그니처 변경 (mentions → mention_count)

## 마이그레이션 과정

1. Phase 1 프로세스 중지
2. 기존 파일 백업: `poc/data/backup_20260104/`
3. 마이그레이션 스크립트 실행: `migrate_checkpoint_v4.py`
4. 파일 이름 변경:
   - `phase1_checkpoint.json` → `phase1_checkpoint.json.bak`
   - `phase1_checkpoint_v4.json` → `phase1_checkpoint.json`
5. Phase 1 재시작

## 롤백 방법

```bash
# 백업에서 복원
cp poc/data/backup_20260104/phase1_checkpoint.json poc/data/
cp poc/data/backup_20260104/pending_queue.jsonl poc/data/
cp poc/data/backup_20260104/status.json poc/data/
rm poc/data/mentions.jsonl

# V3 checkpoint.py로 되돌리기 (git에서)
git checkout poc/app/core/checkpoint.py
```

## 관련 파일
- `poc/app/core/checkpoint.py` - V4 구조
- `poc/scripts/archivist_fullscale_v3.py` - V4 대응
- `poc/scripts/migrate_checkpoint_v4.py` - 마이그레이션 스크립트
- `poc/data/backup_20260104/` - V3 백업
