# Archivist 체크포인트 시스템 재설계

**날짜**: 2026-01-03
**상태**: 구현 예정

---

## 1. 현재 문제점

| 문제 | 영향 |
|------|------|
| 상황판 없음 | 진행 상태 파악 불가 |
| PENDING 1,000개만 저장 | 나머지 영구 손실 |
| Phase 완료 여부 불명확 | Phase 2가 시작해도 되는지 모름 |
| 속도/에러 로깅 없음 | 문제 발생 시 원인 파악 불가 |
| 이어하기 불안정 | 재시작 시 데이터 정합성 문제 |

---

## 2. 새 체크포인트 구조

### 2.1 상황판 파일 (status.json)
```json
{
  "phase1": {
    "status": "running|completed|error",
    "started_at": "2026-01-03T10:00:00",
    "updated_at": "2026-01-03T12:00:00",
    "completed_at": null,
    "total_files": 76090,
    "processed_files": 1500,
    "progress_percent": 1.97,
    "speed_files_per_hour": 3500,
    "eta_hours": 21.3,
    "errors": []
  },
  "phase2": {
    "status": "waiting|running|completed|error",
    "started_at": null,
    "total_pending": 0,
    "processed_pending": 0,
    "progress_percent": 0
  }
}
```

### 2.2 Phase 1 체크포인트 (phase1_checkpoint.json)
```json
{
  "version": 1,
  "timestamp": "2026-01-03T12:00:00",
  "processed_files": ["file1.json", "file2.json", ...],
  "registry": {
    "entities": [...],
    "next_id": 1234
  }
}
```

### 2.3 PENDING 전용 파일 (pending_queue.jsonl)
- **JSONL 형식** (한 줄 = 하나의 pending item)
- **Append-only** - 추가만 함, 수정/삭제 안 함
- Phase 2가 읽고 별도로 처리 완료 표시

```jsonl
{"id": 1, "text": "Caesar", "entity_type": "person", "candidates": [...], "processed": false}
{"id": 2, "text": "Rome", "entity_type": "location", "candidates": [...], "processed": false}
```

### 2.4 Phase 2 결과 (phase2_decisions.jsonl)
- **JSONL 형식**
- Phase 1 데이터 수정 안 함, 별도 저장

```jsonl
{"pending_id": 1, "decision": "LINK_EXISTING", "linked_entity_id": 42, "timestamp": "..."}
{"pending_id": 2, "decision": "CREATE_NEW", "new_entity_id": 1235, "timestamp": "..."}
```

---

## 3. 파일 구조

```
poc/data/
├── status.json              # 상황판 (실시간 업데이트)
├── phase1_checkpoint.json   # Phase 1 체크포인트
├── pending_queue.jsonl      # PENDING 큐 (append-only)
├── phase2_decisions.jsonl   # Phase 2 결정 (append-only)
└── archivist_results/       # 최종 결과
    └── final_merged.json    # Phase 1 + Phase 2 머지 결과
```

---

## 4. 동작 흐름

### Phase 1
```
시작
  ↓
status.json 업데이트 (status: "running")
  ↓
파일 처리 루프:
  - 엔티티 추출
  - 결정 (CREATE_NEW / LINK_EXISTING / PENDING)
  - PENDING이면 → pending_queue.jsonl에 append
  - 50개마다 → phase1_checkpoint.json 저장
  - 100개마다 → status.json 업데이트
  ↓
완료 시 status.json (status: "completed")
```

### Phase 2
```
시작
  ↓
status.json 확인 (phase1.status == "completed" 또는 "running")
  ↓
pending_queue.jsonl 읽기
  ↓
처리 안 된 항목만 필터링
  ↓
Qwen으로 결정
  ↓
phase2_decisions.jsonl에 append
  ↓
status.json 업데이트
```

---

## 5. 구현 순서

- [ ] 5.1 StatusManager 클래스 구현
- [ ] 5.2 PendingQueue 클래스 구현 (JSONL append-only)
- [ ] 5.3 Phase1Processor 수정
- [ ] 5.4 Phase2Processor 수정
- [ ] 5.5 테스트 (100개 파일)
- [ ] 5.6 전체 실행

---

## 6. 이어하기 보장

### Phase 1 재시작 시
1. `phase1_checkpoint.json` 로드
2. `processed_files` 목록 확인
3. 이미 처리된 파일 스킵
4. 이어서 처리

### Phase 2 재시작 시
1. `pending_queue.jsonl` 전체 읽기
2. `phase2_decisions.jsonl` 읽기 → 처리된 ID 수집
3. 처리 안 된 pending만 처리

---

## 7. 모니터링

### status.json 실시간 확인
```bash
watch -n 5 cat poc/data/status.json
```

### 진행률 확인 스크립트
```python
# check_progress.py
import json
with open("poc/data/status.json") as f:
    s = json.load(f)
    p1 = s["phase1"]
    print(f"Phase 1: {p1['processed_files']}/{p1['total_files']} ({p1['progress_percent']:.1f}%)")
    print(f"Speed: {p1['speed_files_per_hour']} files/hour")
    print(f"ETA: {p1['eta_hours']:.1f} hours")
```

---

*이 설계를 기반으로 구현 진행*
