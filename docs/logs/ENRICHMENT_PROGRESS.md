# Enrichment Pipeline 진행 상황

**작성일**: 2026-01-08
**최종 수정**: 2026-01-10 22:53

---

## 1. 완료된 작업

### 1.1 기존 V0 이벤트 엔리치먼트 적용
- **파일**: `poc/data/enrichment_results/full_sync_20260108_012350.json`
- **건수**: 10,428개
- **모델**: gpt-5.1-chat-latest
- **비용**: $39.52
- **소요시간**: 110분
- **적용**: `apply_enrichment.py --apply` 실행 완료
  - events 테이블 업데이트: 10,427개
  - locations 테이블 생성: 9,491개

### 1.2 NER 이벤트 DB 임포트
- **소스**: `poc/data/integrated_ner_full/aggregated/events.json`
- **원본**: 91,977개 (연도 없는 것 50,725개 포함)
- **임포트**: 41,241개 (연도 있는 것만)
- **슬러그 형식**: `ner-{base-slug}-{index}`
- **스크립트**: `import_to_v1_db.py --force-all --events-only`

### 1.3 현재 DB 상태
```
총 이벤트: 51,669개
├── V0 기존: 10,428개 (enriched by gpt-5.1)
└── NER 신규: 41,241개 (미처리)
```

---

## 2. 다음 작업

### 2.1 NER 이벤트 엔리치먼트 (현재 단계)
- **대상**: 41,241개 NER 이벤트
- **목적**: title_clean, year 보정, location, category 등 추출

**모델 비교 테스트 필요**:
| 모델 | 예상 비용 | 예상 시간 | 품질 |
|-----|----------|----------|------|
| gpt-5.1-chat-latest | ~$160 | ~7시간 | 최고 |
| gpt-5-nano | ~$30-40 | ~2-3시간 | 미확인 |
| gemma2:9b (로컬) | $0 | ~27일 | 미확인 |

**테스트 결과** (2026-01-08 18:07):
| 모델 | 성공률 | 평균 시간 | 41K 예상 비용 |
|-----|-------|----------|-------------|
| gpt-5.1 | 10/10 | 2.8초 | ~$74 |
| gpt-5-nano | 0/10 (에러) | - | - |
| gemma2:9b | 10/10 | 35초 | $0 |

**선택**: gpt-5.1-chat-latest (품질 우선)

**완료** (2026-01-09 02:18):
- 결과 파일: `poc/data/enrichment_results/full_sync_20260108_181800.json`
- 처리: 41,241개
- 성공: 41,235개 (99.99%)
- 에러: 6개
- 소요 시간: 480분 (8시간)
- 토큰: 입력 39,887,380 / 출력 9,455,681
- **실제 비용: $155.42**

**DB 적용 완료** (2026-01-09 06:35):
- 업데이트: 41,235건
- 위치 생성/연결: 24,352건
- 백업 테이블: events_backup_20260109_063310

### 2.2 매칭/통합 (Reconciliation) ✅
- **목적**: V0 이벤트와 NER 이벤트 중복 매칭 및 통합
- **스크립트**: `reconcile_v2.py` (신규 작성)
- **완료** (2026-01-09 15:38):
  - 전체 매칭: 4,251건
  - 정확 매칭 (제목+연도 100%): 2,360건
  - 위치 매칭: 386건 (자동) + 703건 (AI 검증)
  - AI 거부: 658건
  - **자동 통합**: 3,449건
- **DB 적용 완료**: 3,156건 병합됨 (slug에 `merged-` 접두어)

### 2.3 Event-Source 연결 ✅
- **목적**: 이벤트와 원문 소스 연결 (text_mentions 테이블)
- **스크립트**: `link_ner_sources.py` (신규 작성)
- **완료** (2026-01-09 18:55):
  - NER 이벤트: 38,085개 100% 연결
  - V0 이벤트 (병합된 것): 1,501개 연결
  - 총 event mentions: 72,674개
- **전체 커버리지**: 81.6% (39,586 / 48,513)

### 2.4 SQLAlchemy 모델 업데이트
- `events` 모델에 enrichment 필드 추가
  - enriched_by, enriched_at, enrichment_version
- DB 마이그레이션 002는 이미 적용됨, 모델 코드만 업데이트 필요

---

## 3. Phase 3: Location & Person 엔리치먼트

### 3.1 Locations 엔리치먼트 ✅
- **대상**: 36,852개 (이름 있고 country 없는 것)
- **모델**: gpt-5.1-chat-latest
- **추출 항목**: country, region, type
- **결과 파일**: `poc/data/enrichment_results/locations_20260110_201801.json`
- **완료** (2026-01-10 20:32):
  - 처리: 36,852개
  - 성공: 36,845개 (99.98%)
  - 에러: 7개
  - 토큰: 입력 2,092,822 / 출력 3,384,411
  - **실제 비용: $39.08**
- **DB 적용 완료** (2026-01-10 20:35):
  - 업데이트: 36,826개
  - country 보유: 36,798개 (90.6%)
  - region 보유: 36,825개 (90.7%)
  - 백업 테이블: locations_backup_20260110_203224

### 3.2 Persons 엔리치먼트 ✅
- **대상**: mention >= 5, birth_year 없음
- **모델**: gpt-5.1-chat-latest
- **추출 항목**: birth_year, death_year, role, era, is_real_person
- **스크립트**: `poc/scripts/enrich_persons_llm.py`

**1차 실행** (mention >= 10):
- **결과 파일**: `poc/data/enrichment_results/persons_20260110_204144.json`
- **완료** (2026-01-10 20:41):
  - 처리: 2,011명 (100% 성공)
  - 토큰: 입력 413,434 / 출력 155,724
  - **비용: $2.59**
- **DB 적용**: 774명 실제 인물, 1,237개 가상 스킵

**2차 실행** (mention >= 5):
- **결과 파일**: `poc/data/enrichment_results/persons_20260110_215850.json`
- **완료** (2026-01-10 22:00):
  - 처리: 6,182명 (100% 성공)
  - 토큰: 입력 1,273,348 / 출력 489,395
  - **비용: $8.08**
- **DB 적용**: 2,625명 실제 인물, 3,557개 가상 스킵

**3차 실행** (mention >= 3):
- **결과 파일**: `poc/data/enrichment_results/persons_20260110_222744.json`
- **완료** (2026-01-10 22:51):
  - 처리: 14,760명 (100% 성공)
  - 토큰: 입력 3,038,835 / 출력 1,216,759
  - **비용: $19.76**
- **DB 적용 완료** (2026-01-10 22:52):
  - 실제 인물 업데이트: 6,109명 (41%)
  - 가상/비인물 스킵: 8,651개 (59%)
  - 백업 테이블: persons_backup_20260110_204240

### 3.3 최종 DB 상태
```
Locations: 40,613개
├── 좌표 있음: 100%
├── country 있음: 90.6% ✅
├── region 있음: 90.7% ✅
└── Event 연결: 65.9%

Persons (mention >= 3): 21,963명
├── birth_year 있음: 55.7% ✅
├── death_year 있음: 56.1% ✅
└── role 있음: 100% ✅

총 실제 인물 엔리치: 9,508명 (774 + 2,625 + 6,109)
가상/비인물 자동 필터: 13,445개 (1,237 + 3,557 + 8,651)
```

---

## 4. 파일 목록

### 스크립트
| 파일 | 설명 |
|-----|------|
| `poc/scripts/import_to_v1_db.py` | NER 데이터 DB 임포트 |
| `poc/scripts/apply_enrichment.py` | 이벤트 엔리치먼트 결과 DB 적용 |
| `poc/scripts/apply_locations_enrichment.py` | 위치 엔리치먼트 결과 DB 적용 |
| `poc/scripts/enrich_events_llm.py` | OpenAI API 이벤트 엔리치먼트 |
| `poc/scripts/enrich_locations_llm.py` | OpenAI API 위치 엔리치먼트 |
| `poc/scripts/enrich_persons_llm.py` | OpenAI API 인물 엔리치먼트 |
| `poc/scripts/reconcile_v2.py` | 이벤트 매칭/통합 V2 |
| `poc/scripts/link_ner_sources.py` | NER 이벤트-소스 연결 |
| `poc/scripts/generate_person_story.py` | Person Story 생성 |

### 데이터
| 경로 | 설명 |
|-----|------|
| `poc/data/integrated_ner_full/aggregated/` | NER 추출 결과 (JSON) |
| `poc/data/enrichment_results/` | 엔리치먼트 결과 |
| `poc/data/reconcile_results/` | 매칭 결과 |
| `poc/data/stories/` | 생성된 스토리 |

### 마이그레이션
| 파일 | 설명 | 상태 |
|-----|------|------|
| `backend/alembic/versions/001_v1_schema.py` | V1 스키마 | 적용됨 |
| `backend/alembic/versions/002_add_enrichment_tracking.py` | 엔리치먼트 추적 필드 | 적용됨 |

---

## 5. 비용 기록

| 작업 | 모델 | 건수 | 비용 | 날짜 |
|-----|------|-----|------|------|
| V0 이벤트 엔리치먼트 | gpt-5.1-chat-latest | 10,428 | $39.52 | 2026-01-08 |
| NER 이벤트 엔리치먼트 | gpt-5.1-chat-latest | 41,241 | $155.42 | 2026-01-09 |
| Reconciliation AI 검증 | gpt-5.1-chat-latest | 1,505 | ~$2 | 2026-01-09 |
| Locations 엔리치먼트 | gpt-5.1-chat-latest | 36,852 | $39.08 | 2026-01-10 |
| Persons 엔리치먼트 (>=10) | gpt-5.1-chat-latest | 2,011 | $2.59 | 2026-01-10 |
| Persons 엔리치먼트 (>=5) | gpt-5.1-chat-latest | 6,182 | $8.08 | 2026-01-10 |
| Persons 엔리치먼트 (>=3) | gpt-5.1-chat-latest | 14,760 | $19.76 | 2026-01-10 |
| **누적 합계** | | | **$266.45** |

---

## 6. 변경 이력

| 날짜 | 내용 |
|-----|------|
| 2026-01-08 17:50 | 문서 생성, 모델 비교 테스트 예정 |
| 2026-01-09 02:18 | NER 이벤트 엔리치먼트 완료 ($155.42) |
| 2026-01-09 06:35 | NER 엔리치먼트 DB 적용 완료 |
| 2026-01-09 15:38 | Reconciliation 완료 (3,156건 병합) |
| 2026-01-09 18:55 | Event-Source 연결 완료 (81.6% 커버리지) |
| 2026-01-09 19:30 | Locations/Persons 엔리치먼트 시작 |
| 2026-01-10 20:32 | Locations 엔리치먼트 완료 ($39.08) |
| 2026-01-10 20:35 | Locations DB 적용 완료 (90.6% country 커버리지) |
| 2026-01-10 20:41 | Persons 엔리치먼트 완료 ($2.59) |
| 2026-01-10 20:43 | Persons DB 적용 완료 (774명 실제 인물, 1,237 가상 스킵) |
| 2026-01-10 22:00 | Persons 확장 엔리치먼트 (mention >= 5) 완료 ($8.08) |
| 2026-01-10 22:01 | Persons 확장 DB 적용 완료 (2,625명 추가) |
| 2026-01-10 22:51 | Persons 3차 엔리치먼트 (mention >= 3) 완료 ($19.76) |
| 2026-01-10 22:52 | Persons 3차 DB 적용 완료 (6,109명 추가) |
| 2026-01-10 22:53 | **Phase 3 완료** - 총 비용 $266.45 |
