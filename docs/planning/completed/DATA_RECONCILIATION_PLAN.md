# 데이터 통합 및 정리 계획

**Date**: 2026-01-08
**Status**: 계획 수립

---

## 1. 현재 데이터 상태

### 1.1 4분면 분류

|  | **엔리치먼트 O** | **엔리치먼트 X** |
|--|-----------------|-----------------|
| **원본 O** | 910개 (완벽) | 124,080개 (버려진 NER) |
| **원본 X** | 9,518개 (고아 DB) | 0 |

### 1.2 데이터 위치

```
DB (PostgreSQL):
├── events: 10,428개 (엔리치먼트 완료)
│   ├── with source: 910개
│   └── orphan: 9,518개
└── text_mentions: 4,675개 event 멘션

NER 원본 (파일):
├── poc/data/integrated_ner_full/minimal_batch_*_output.jsonl
└── 124,990개 이벤트 (source 연결 정보 포함)
```

---

## 2. 통합 전략

### Phase 1: 매칭 (3번 ↔ 2번 그룹)

**목표**: 고아 DB 이벤트(9,518개)와 NER 추출 이벤트(124,080개) 매칭

```
DB 고아 이벤트 (엔리치먼트 O, 원본 X)
        ↓ fuzzy matching
NER 이벤트 (엔리치먼트 X, 원본 O)
        ↓
┌───────────────────────────────────────┐
│ 매칭 성공 → source 연결 추가          │
│ 매칭 실패 (DB) → 고아로 유지          │
│ 매칭 실패 (NER) → 신규 이벤트 후보    │
└───────────────────────────────────────┘
```

#### 매칭 알고리즘

```python
def match_events(db_event, ner_event):
    score = 0

    # 1. 제목 유사도 (40%)
    title_sim = fuzzy_match(db_event.title, ner_event.name)
    score += title_sim * 0.4

    # 2. 연도 근접성 (30%)
    if db_event.year and ner_event.year:
        year_diff = abs(db_event.year - ner_event.year)
        year_score = max(0, 100 - year_diff * 10)  # 10년 차이마다 -10점
        score += year_score * 0.3

    # 3. 관련 인물 겹침 (20%)
    if ner_event.persons_involved:
        person_overlap = check_person_overlap(db_event, ner_event)
        score += person_overlap * 0.2

    # 4. 관련 장소 겹침 (10%)
    if ner_event.locations_involved:
        location_overlap = check_location_overlap(db_event, ner_event)
        score += location_overlap * 0.1

    return score

# 판정 기준
if score >= 85:
    return "AUTO_MATCH"      # 자동 연결
elif score >= 60:
    return "REVIEW"          # 수동 검토 필요
else:
    return "NO_MATCH"        # 매칭 안 됨
```

#### 예상 결과

| 결과 | 예상 비율 | 예상 건수 |
|------|----------|----------|
| AUTO_MATCH (≥85%) | ~30% | ~2,800개 |
| REVIEW (60-85%) | ~20% | ~1,900개 |
| NO_MATCH (<60%) | ~50% | ~4,800개 |

---

### Phase 2: Source 연결 생성

매칭된 이벤트에 source 연결 추가:

```sql
-- 매칭 결과를 text_mentions에 추가
INSERT INTO text_mentions (
    entity_type, entity_id, source_id,
    mention_text, confidence, extraction_model
)
SELECT
    'event',
    match.db_event_id,
    ner.source_id,
    ner.event_name,
    match.score / 100.0,
    'reconciliation'
FROM matched_events match
JOIN ner_events ner ON match.ner_event_id = ner.id;
```

---

### Phase 3: 신규 이벤트 임포트

매칭 안 된 NER 이벤트 중 품질 좋은 것 임포트:

```
NER 매칭 안 된 이벤트: ~121,000개
        ↓ 필터링
┌─────────────────────────────────────┐
│ 필터 조건:                          │
│ - confidence >= 0.7                 │
│ - name 길이 >= 5                    │
│ - year가 있거나 persons_involved 있음│
└─────────────────────────────────────┘
        ↓
임포트 후보: ~30,000-50,000개 (추정)
```

#### 임포트 데이터 구조

```python
new_event = {
    "title": ner_event["name"],
    "date_start": ner_event.get("year"),
    "date_end": ner_event.get("year"),
    # 엔리치먼트 전이므로 나머지는 NULL
    "primary_location_id": None,
    "date_precision": None,
    "era": None,
    # source 연결은 바로 생성
    "source_id": ner_event["source_id"]
}
```

---

## 3. 추후 작업

### 3.1 엔리치먼트 대상 결정

통합 후 데이터 상태:

| 그룹 | 건수 | 엔리치먼트 | Source | 조치 |
|------|------|-----------|--------|------|
| 기존 완벽 | 910 | ✅ | ✅ | 없음 |
| 기존+매칭 | ~2,800 | ✅ | ✅ (추가됨) | 없음 |
| 기존 고아 | ~6,700 | ✅ | ❌ | 유지 (source 없이) |
| 신규 임포트 | ~40,000 | ❌ | ✅ | **엔리치먼트 필요** |

### 3.2 신규 이벤트 엔리치먼트 옵션

**Option A: 전체 엔리치먼트 (~$150)**
```
40,000개 × $0.0038 = ~$152
```
- 모든 신규 이벤트에 좌표, 연도, era 등 추가
- 품질 일관성 확보

**Option B: 선택적 엔리치먼트**
```
사용자가 조회하는 이벤트만 on-demand 엔리치먼트
또는 특정 era/category만 우선 처리
```
- 비용 절감
- 필요한 것만 처리

**Option C: 기본 정보만 유지**
```
NER 데이터 그대로 사용
- name → title
- year → date_start, date_end
- locations_involved[0] → 위치 매칭 시도
```
- 추가 비용 없음
- 품질은 낮음

### 3.3 엔리치먼트 우선순위 (Option B 선택 시)

```
Priority 1: Classical/Ancient 시대 이벤트
  - 역사적 중요도 높음
  - 좌표 오류 가능성 높음

Priority 2: Battle/War 카테고리
  - 지도 표시에 중요
  - 위치 정확도 필요

Priority 3: 나머지
  - 필요 시 처리
```

---

## 4. 실행 계획

### CP-R1: 매칭 스크립트 개발
- [ ] NER 데이터 로더 구현
- [ ] fuzzy matching 알고리즘 구현
- [ ] 매칭 결과 저장 테이블 생성

### CP-R2: 매칭 실행
- [ ] 9,518개 DB 이벤트 × 124,080개 NER 이벤트 매칭
- [ ] 결과 분석 (AUTO_MATCH, REVIEW, NO_MATCH)
- [ ] 매칭 품질 샘플 검토

### CP-R3: Source 연결 적용
- [ ] AUTO_MATCH 결과 → text_mentions 추가
- [ ] 연결 성공률 확인

### CP-R4: 신규 이벤트 임포트
- [ ] 임포트 대상 필터링
- [ ] events 테이블에 추가
- [ ] source 연결 생성

### CP-R5: 결과 보고
- [ ] 최종 데이터 현황 정리
- [ ] 엔리치먼트 대상 목록 생성
- [ ] 사용자에게 엔리치먼트 옵션 제시

---

## 5. 예상 결과

### Before (현재)
```
Events: 10,428개
├── with source: 910개 (8.7%)
└── orphan: 9,518개 (91.3%)

NER 데이터: 124,990개 (활용 안 됨)
```

### After (통합 후)
```
Events: ~50,000개 (추정)
├── 엔리치먼트 O + source O: ~3,700개
├── 엔리치먼트 O + source X: ~6,700개
└── 엔리치먼트 X + source O: ~40,000개 ← 엔리치먼트 대상
```

---

## 6. 로컬 모델 엔리치먼트 옵션

### 6.1 하드웨어 사양
- GPU: RTX 3060 6GB VRAM
- RAM: 32GB
- 사용 가능 모델: 7B 이하 (4-bit 양자화)

### 6.2 후보 모델

| 모델 | 크기 | VRAM 필요 | 속도 | 품질 |
|------|------|----------|------|------|
| **Llama 3.1 8B Q4** | 4.7GB | ~5GB | ~10 tok/s | 좋음 |
| **Mistral 7B Q4** | 4.1GB | ~5GB | ~12 tok/s | 좋음 |
| **Phi-3 Mini 3.8B** | 2.3GB | ~3GB | ~20 tok/s | 보통 |
| **Qwen2 7B Q4** | 4.2GB | ~5GB | ~11 tok/s | 좋음 |

### 6.3 예상 처리 시간

```
40,000 이벤트 × (입력 ~500 tok + 출력 ~200 tok) = 28M tokens

Llama 3.1 8B Q4 (10 tok/s):
  28M / 10 = 2.8M 초 = ~780 시간 = ~32일

병렬 처리 (batch size 4):
  ~8일

Phi-3 Mini (20 tok/s):
  ~4일 (단일) / ~1일 (병렬)
```

### 6.4 로컬 vs API 비교

| 항목 | 로컬 (Llama 3.1 8B) | API (GPT-5.1) |
|------|-------------------|---------------|
| 비용 | $0 (전기세만) | ~$150 |
| 시간 | ~8일 | ~4시간 |
| 품질 | 중상 | 최상 |

### 6.5 하이브리드 전략 (권장)

```
Step 1: 로컬 모델로 기본 엔리치먼트
  - 연도 추출 (year_start, year_end)
  - 카테고리 분류 (battle, treaty, etc.)
  - era 분류

Step 2: 실패 건만 API로 처리
  - 위치 좌표 (geocoding 어려움)
  - confidence 낮은 건
```

**예상 비용**: API $30~50 (실패 건만)

---

## 7. 비용 요약

| 단계 | 작업 | 비용 |
|------|------|------|
| 이미 지출 | NER 추출 | $47 |
| 이미 지출 | 기존 엔리치먼트 | $40 |
| CP-R1~R5 | 매칭 + 임포트 | $0 |
| 추후 (Option A) | API 전체 엔리치먼트 | ~$150 |
| 추후 (Option B) | 로컬 + API 하이브리드 | ~$30-50 |
| 추후 (Option C) | 로컬만 | $0 |
| **합계** | | **$87 + $0~150** |

---

## 7. 파일 위치

| Component | Path |
|-----------|------|
| 이 문서 | `docs/planning/DATA_RECONCILIATION_PLAN.md` |
| 매칭 스크립트 (예정) | `poc/scripts/reconcile_events.py` |
| NER 원본 | `poc/data/integrated_ner_full/minimal_batch_*_output.jsonl` |

---

## 8. 다음 단계

1. **이 계획 승인**
2. **CP-R1 시작**: 매칭 스크립트 개발
3. **매칭 테스트**: 1개 배치로 파일럿
4. **전체 실행**
5. **결과 보고 후 엔리치먼트 결정**
