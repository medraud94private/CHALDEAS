# Archivist PoC 설계 결함 보고서

**날짜**: 2026-01-03
**작성자**: Claude
**상태**: 실패 분석 완료

---

## 1. 개요

76,000개 파일(~50GB)을 처리하기 위한 Archivist Full-Scale Processing 시스템 구현 중 다수의 설계 결함이 발견되어 작업이 중단됨.

---

## 2. 발생한 문제들 (시간순)

### 2.1 Qwen3 Thinking Mode 문제 (해결됨)

**증상:**
- 모든 엔티티가 `PENDING` 상태로 처리됨
- "Qwen error:" 빈 에러 메시지 출력

**원인:**
```python
# 잘못된 코드 - /api/generate 사용
response = await client.post(
    f"{settings.ollama_base_url}/api/generate",
    json={"model": model, "prompt": prompt, "think": False}  # think:false 작동 안 함
)
```

**해결:**
```python
# 수정된 코드 - /api/chat 사용
response = await client.post(
    f"{settings.ollama_base_url}/api/chat",
    json={
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "think": False  # /api/chat에서만 작동
    }
)
```

**교훈:** Ollama API 문서를 충분히 확인하지 않음. `/api/generate`와 `/api/chat`의 차이점 미숙지.

---

### 2.2 Phase 2 병렬 처리 - Candidates 누락 (해결됨)

**증상:**
- Phase 2가 모든 결정을 `CREATE_NEW`로 처리
- 처리 속도가 비정상적으로 빠름 (233,000/hour)

**원인:**
```python
# fullscale.py - candidates 저장 누락
pending_items.append({
    "text": item.get("text", ""),
    "entity_type": item.get("entity_type", ""),
    "context": item.get("context", "")[:500],
    "source": "pending_queue"
    # candidates 필드 누락!
})
```

Phase 2 코드:
```python
candidates = item.get("candidates", [])
if not candidates:
    return {"decision": "CREATE_NEW", ...}  # candidates 없으면 바로 리턴
```

**해결:**
```python
pending_items.append({
    "text": item.get("text", ""),
    "entity_type": item.get("entity_type", ""),
    "context": item.get("context", "")[:500],
    "candidates": item.get("candidates", []),  # 추가됨
    "source": "pending_queue"
})
```

**교훈:** 새 스크립트 작성 시 데이터 흐름 전체를 검증하지 않음.

---

### 2.3 Phase 2 병렬 처리 - 체크포인트 제한 (미해결, 치명적)

**증상:**
- Phase 1이 33,790개 PENDING 생성
- Phase 2가 12,007개만 처리
- 나머지 21,783개는 처리되지 않음

**원인:**
```python
# fullscale.py - 마지막 1,000개만 저장
for item in self.archivist.pending_queue[-1000:]:  # 문제!
    pending_items.append({...})
```

**결과:**
- 체크포인트가 저장될 때마다 이전 pending items 덮어씌워짐
- Phase 2는 항상 "최신 1,000개"만 볼 수 있음
- 나머지 pending items는 영구 손실

**이것이 치명적인 이유:**
1. Phase 1 속도: ~3,500 files/hour → ~77,000 pending/hour 생성
2. Phase 2 속도: ~1,429 items/hour 처리
3. 체크포인트 저장 주기: 50 files마다 (~1분마다)
4. 매 분마다 새 1,000개로 덮어씌워짐 → 대부분 pending items 손실

**미해결 상태:** 근본적인 아키텍처 재설계 필요

---

### 2.4 GPU 사용 여부 혼란

**증상:**
- nvidia-smi에서 Ollama 프로세스 안 보임
- GPU 메모리 2.2GB (모델 미로드 상태)

**원인:**
- Ollama 기본 설정: 5분 미사용 시 모델 자동 언로드
- Phase 2가 1,000개 빠르게 처리 후 대기 → 5분 경과 → 모델 언로드

**혼란의 원인:**
- Phase 2가 "빨리 끝난" 이유를 제대로 분석하지 않음
- "5분 대기" = "할 일 없음" = "Phase 1 따라잡음" 또는 "설계 결함" 가능성 미검토

---

### 2.5 로깅 시스템 부재

**증상:**
- stdout 출력만 존재
- 프로세스 상태 추적 불가
- 문제 발생 시 원인 분석 어려움

**누락된 로깅:**
- 타임스탬프 없음
- 파일 기반 로그 없음
- 처리 속도/진행률 주기적 기록 없음
- 에러 발생 시 상세 정보 없음

---

## 3. 근본 원인 분석

### 3.1 검증 부족
- 새 스크립트 작성 후 소규모 테스트만 수행
- "50개 파일 테스트 성공" → 바로 76,000개 투입
- 데이터 흐름 전체 검증 미실시

### 3.2 설계 단계 생략
- 요구사항: "3일간 자동 실행"
- 실제: 즉흥적으로 스크립트 작성
- 아키텍처 문서화 없음
- 엣지 케이스 고려 없음

### 3.3 병렬 처리 복잡성 과소평가
- Phase 1과 Phase 2 간 데이터 공유 방식 미숙고
- 체크포인트 파일을 "메시지 큐"처럼 사용하려 함
- 실제로는 "스냅샷"으로만 동작 → 데이터 손실

### 3.4 모니터링 부재
- 실시간 상태 확인 수단 없음
- 문제 발생해도 사용자가 질문하기 전까지 모름

---

## 4. 올바른 설계 방향

### 4.1 데이터 흐름
```
Phase 1 (CPU)
    ↓
[별도 Pending Queue 파일] ← 전체 저장, append-only
    ↓
Phase 2 (GPU) ← 처리 완료된 항목 마킹
```

### 4.2 필요한 구성요소
1. **Pending Queue 전용 저장소**: SQLite 또는 별도 JSON 파일
2. **처리 상태 추적**: 각 pending item의 처리 여부 기록
3. **로깅 시스템**: 파일 기반, 타임스탬프, 주기적 통계
4. **모니터링**: 진행률, 에러 카운트, 예상 완료 시간

### 4.3 Phase 2 재설계 옵션

**옵션 A: 순차 실행 (단순함)**
- Phase 1 완료 후 Phase 2 실행
- 전체 pending queue를 한 번에 처리
- 복잡도 낮음, 신뢰성 높음

**옵션 B: 병렬 실행 (복잡함)**
- 별도 pending queue 저장소 필요
- Phase 1: append, Phase 2: consume & mark
- Producer-Consumer 패턴 구현 필요

---

## 5. 현재 상태

| 항목 | 상태 |
|------|------|
| Phase 1 스크립트 | 중단됨, 수정 필요 |
| Phase 2 병렬 스크립트 | 중단됨, 재설계 필요 |
| 체크포인트 | 1,544 파일 처리 시점 |
| Pending 손실 | 약 20,000+ 항목 추정 |

---

## 6. 다음 단계 권장사항

1. **즉시**: 현재 체크포인트 백업
2. **단기**: Phase 1 단독 실행으로 전환 (병렬 포기)
3. **중기**: 로깅 시스템 추가
4. **장기**: 병렬 처리 재설계 (옵션 B)

---

## 7. 교훈 요약

1. **"작동함"과 "올바름"은 다르다** - 테스트 통과가 정확성을 보장하지 않음
2. **데이터 흐름을 시각화하라** - 특히 병렬/비동기 시스템에서
3. **로깅은 선택이 아닌 필수** - 문제 발생 시 유일한 단서
4. **대규모 작업 전 소규모 E2E 테스트** - 50개가 아닌 1,000개로 테스트했어야 함
5. **복잡성을 과소평가하지 마라** - "그냥 병렬로 돌리면 되지"는 함정

---

*이 문서는 실패 분석을 위해 작성되었으며, 향후 유사한 문제 방지를 목적으로 함.*
