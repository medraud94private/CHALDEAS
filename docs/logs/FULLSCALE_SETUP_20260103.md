# Archivist Full-Scale Processing Setup

**날짜**: 2026-01-03
**작업자**: Claude

---

## 1. 데이터 규모

| 소스            | 파일 수  | 크기    |
|-----------------|----------|---------|
| British Library | 63,985   | 42 GB   |
| Gutenberg       | 12,031   | ~6 GB   |
| Perseus         | 2,482    | -       |
| Britannica 1911 | 2,000    | -       |
| 기타 15개 소스  | ~600     | ~1 GB   |
| **합계**        | **76,120** | **~50 GB** |

---

## 2. 처리 전략: 2-Phase Approach

### Phase 1: Fast Mode (규칙 기반)
- **방식**: LLM 없이 규칙 기반 매칭
- **속도**: ~4,500 files/hour
- **예상 시간**: ~17시간
- **결과**:
  - CREATE_NEW: ~40% (새 엔티티)
  - LINK_EXISTING: ~15% (확실한 매칭)
  - PENDING: ~45% (애매한 경우)

### Phase 2: LLM Review
- **방식**: PENDING 항목을 Qwen3:8b로 리뷰
- **대상**: Phase 1에서 PENDING 처리된 항목
- **예상 시간**: ~1-2일 (PENDING 수에 따라)

### 총 예상 시간: ~3일

---

## 3. 실행 방법

### 옵션 A: 2단계 자동 실행 (권장)
```batch
cd C:\Projects\Chaldeas\poc
run_fullscale_2phase.bat
```

### 옵션 B: Phase 1만 실행
```batch
cd C:\Projects\Chaldeas\poc
python -u scripts/archivist_fullscale.py
```

### 옵션 C: LLM 모드로 실행 (느림)
```batch
cd C:\Projects\Chaldeas\poc
python -u scripts/archivist_fullscale.py --slow
```

---

## 4. 생성된 파일

| 파일 | 용도 |
|------|------|
| `poc/scripts/archivist_fullscale.py` | 메인 처리 스크립트 |
| `poc/scripts/archivist_review_pending.py` | Phase 2 PENDING 리뷰 |
| `poc/run_fullscale_2phase.bat` | 2단계 자동 실행 |
| `poc/data/archivist_checkpoint.json` | 체크포인트 (재시작 가능) |
| `poc/data/archivist_results/*.json` | 결과 파일 |

---

## 5. 체크포인트 기능

- **자동 저장**: 100개 파일마다 체크포인트 저장
- **재시작 가능**: 중단 후 이어서 처리 가능
- **리셋**: `--reset` 플래그로 처음부터 시작

---

## 6. 성능 테스트 결과

### Fast Mode (50 파일 테스트)
```
처리 시간: ~40초
속도: 4,556 files/hour
엔티티 처리: 2,302개

결과:
- CREATE_NEW:    948 (41.2%)
- LINK_EXISTING: 294 (12.8%)
- PENDING:       1,060 (46.0%)
```

### 예상 전체 처리 시간
- Phase 1 (Fast): 76,090 / 4,556 = **16.7시간**
- Phase 2 (LLM): PENDING 수 × 2초 ≈ **1-2일**
- **총**: ~3일

---

## 7. 모니터링

### 로그 확인
```batch
type poc\logs\fullscale_2phase_*.log
```

### 진행 상황 확인
```batch
type poc\data\archivist_checkpoint.json | findstr "processed_files total_files"
```

### 현재 통계
```batch
type poc\data\archivist_checkpoint.json | findstr "stats"
```

---

## 8. 주의사항

1. **Ollama 필요**: Phase 2에서 Qwen3:8b 모델 필요
2. **디스크 공간**: 결과 파일 ~100MB 예상
3. **메모리**: 대규모 레지스트리로 메모리 사용량 증가 가능
4. **중단 시**: 자동으로 체크포인트에서 재개

---

## 9. 결론

76,000개 파일을 3일 안에 처리하기 위해 2단계 전략 구현:
1. Fast mode로 빠르게 1차 분류 (~17시간)
2. LLM으로 애매한 케이스 정밀 검토 (~1-2일)

이 방식으로 정확도를 유지하면서 처리 시간을 현실적으로 줄임.
