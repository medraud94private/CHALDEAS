# CHALDEAS V1 작업 계획

## 버전 정의

| 버전 | 설명 | 상태 |
|-----|------|------|
| **V0** | 기존 레거시 구조 | 운영 중 (유지) |
| **V1** | Historical Chain 기반 신규 구조 | 개발 중 |

---

## 작업 원칙

1. **체크포인트 단위 작업**: 각 작업은 명확한 시작/완료 표시
2. **작업 로그 기록**: `docs/logs/V1_WORKLOG.md`에 진행상황 기록
3. **V0 영향 없음**: 기존 서버/API에 영향 주지 않음
4. **테스트 우선**: 각 체크포인트 완료 시 테스트 포함

---

## Phase 1: 데이터 모델 확장

### CP-1.1: V1 모델 디렉토리 구조 생성 ✅ DONE
- [x] `backend/app/models/v1/` 디렉토리 생성
- [x] `backend/app/models/v1/__init__.py` 생성
- [x] `backend/app/api/v1_new/` 디렉토리 생성 (기존 v1과 구분)
- [x] `backend/app/schemas/v1/` 디렉토리 생성
- [x] `backend/app/core/chain/` 디렉토리 생성
- [x] `backend/app/core/extraction/` 디렉토리 생성

**완료**: 2026-01-01
**의존성**: 없음

---

### CP-1.2: Period 모델 생성 ✅ DONE
- [x] `backend/app/models/v1/period.py` 작성
- [x] Period SQLAlchemy 모델 정의
- [x] 초기 시대 데이터 시드 파일 작성
- [x] `backend/app/schemas/v1/period.py` 스키마 작성

**파일 목록**:
```
backend/app/models/v1/period.py
backend/app/schemas/v1/period.py
backend/app/db/seeds/periods.json
```

**완료**: 2026-01-01
**의존성**: CP-1.1

---

### CP-1.3: Location 모델 확장 ✅ DONE
- [x] Location 모델에 계층 필드 추가 설계
- [x] `modern_parent_id`, `historical_parent_id` 필드 추가
- [x] `hierarchy_level`, `valid_from`, `valid_until` 필드 추가
- [x] 헬퍼 메서드 추가 (get_modern_ancestors, get_historical_ancestors, was_valid_in)

**파일 목록**:
```
backend/app/models/location.py (확장)
```

**완료**: 2026-01-01
**의존성**: CP-1.1
**V0 호환성**: 모든 신규 필드는 nullable=True

---

### CP-1.4: Event 모델 확장 ✅ DONE
- [x] Event 모델에 신규 필드 추가
- [x] `temporal_scale` (evenementielle/conjuncture/longue_duree)
- [x] `period_id` (FK → periods)
- [x] `certainty` (fact/probable/legendary/mythological)
- [x] Period 관계 설정

**파일 목록**:
```
backend/app/models/event.py (확장)
```

**완료**: 2026-01-01
**의존성**: CP-1.2
**V0 호환성**: 모든 신규 필드는 nullable=True

---

### CP-1.5: Alembic 마이그레이션 생성 ✅ DONE
- [x] `periods` 테이블 마이그레이션
- [x] `locations` 확장 마이그레이션
- [x] `events` 확장 마이그레이션
- [x] 마이그레이션 테스트 (로컬 DB)

**파일 목록**:
```
backend/alembic/versions/001_v1_schema_initial.py
```

**완료**: 2026-01-07
**의존성**: CP-1.2, CP-1.3, CP-1.4

---

## Phase 2: V1 스키마 재설계 (Batch NER 대응)

> **2026-01-07 대규모 업데이트**: 5.65M NER 엔티티를 수용하고 Historical Chain 개념을 구현하기 위한 통합 스키마 재설계 완료

### CP-2.1: Polity 모델 생성 ✅ DONE
- [x] `backend/app/models/v1/polity.py` 작성
- [x] Polity 모델 정의 (empire, kingdom, dynasty 등)
- [x] 계보 관계 (predecessor, successor)
- [x] 벡터 임베딩 지원

**파일 목록**:
```
backend/app/models/v1/polity.py
```

**완료**: 2026-01-07
**의존성**: CP-1.5

---

### CP-2.2: HistoricalChain 모델 생성 ✅ DONE
- [x] `backend/app/models/v1/chain.py` 작성
- [x] HistoricalChain 모델 정의 (4가지 chain_type)
- [x] ChainSegment 모델 정의
- [x] ChainEntityRole 모델 정의
- [x] 승격 시스템 (user → cached → featured → system)
- [x] 관계 설정 (Person, Location, Period, Event)

**파일 목록**:
```
backend/app/models/v1/chain.py
```

**완료**: 2026-01-07
**의존성**: CP-2.1

---

### CP-2.3: TextMention/EntityAlias 모델 생성 ✅ DONE
- [x] `backend/app/models/v1/text_mention.py` 작성
- [x] TextMention 모델 정의 (NER 출처 추적)
- [x] EntityAlias 모델 정의 (중복 제거)
- [x] ImportBatch 모델 정의 (배치 추적)
- [x] PendingEntity 모델 정의 (해결 대기)

**파일 목록**:
```
backend/app/models/v1/text_mention.py
```

**완료**: 2026-01-07
**의존성**: CP-2.1

---

### CP-2.4: Person/Source 모델 확장 ✅ DONE
- [x] Person 모델 V1 필드 추가
  - canonical_id, role, era, floruit_start/end
  - certainty, embedding, primary_polity_id
  - mention_count, avg_confidence
- [x] Source 모델 V1 필드 추가
  - document_id, document_path, title, original_year, language

**파일 목록**:
```
backend/app/models/person.py
backend/app/models/source.py
```

**완료**: 2026-01-07
**의존성**: CP-2.1
**V0 호환성**: 모든 신규 필드는 nullable=True

---

### CP-2.5: Associations 확장 ✅ DONE
- [x] person_relationships 확장 (strength, valid_from/until, confidence)
- [x] event_relationships 확장 (certainty, evidence_type, confidence)
- [x] polity_relationships 테이블 추가
- [x] person_polities 테이블 추가

**파일 목록**:
```
backend/app/models/associations.py
```

**완료**: 2026-01-07
**의존성**: CP-2.1

---

### CP-2.6: Alembic 마이그레이션 실행 ✅ DONE
- [x] 10개 신규 테이블 생성
- [x] 기존 테이블 컬럼 추가 (IF NOT EXISTS 패턴)
- [x] 성능 인덱스 생성
- [x] 마이그레이션 테스트 완료

**파일 목록**:
```
backend/alembic.ini
backend/alembic/env.py
backend/alembic/versions/001_v1_schema_initial.py
```

**완료**: 2026-01-07
**의존성**: CP-2.5

---

### CP-2.7: 인덱스 최적화 ✅ DONE
- [x] idx_events_temporal_range (시간 범위 쿼리)
- [x] idx_events_period_date (시대별 이벤트)
- [x] idx_event_persons_person (Person Story)
- [x] idx_event_locations_location (Place Story)
- [x] idx_event_rel_causal (Causal Chain)

**완료**: 2026-01-07
**의존성**: CP-2.6

---

## Phase 3: 서비스 레이어

### CP-3.1: Chain 서비스 레이어
- [ ] `backend/app/services/chain_service.py` 작성
- [ ] 체인 생성 로직
- [ ] 승격 로직 (user → cached → featured → system)
- [ ] 캐시 조회 로직

**파일 목록**:
```
backend/app/services/chain_service.py
```

**의존성**: CP-2.2

---

### CP-3.2: 하이브리드 NER 파이프라인
- [ ] `backend/app/core/extraction/` 디렉토리 생성
- [ ] `ner_pipeline.py` 작성
- [ ] spaCy 통합
- [ ] OpenAI 검증 로직
- [ ] 폴백 로직

**파일 목록**:
```
backend/app/core/extraction/__init__.py
backend/app/core/extraction/ner_pipeline.py
```

**의존성**: CP-2.3

---

## Phase 4: 큐레이션 API

### CP-4.1: 큐레이션 엔드포인트
- [ ] `backend/app/api/v1_new/curation.py` 작성
- [ ] POST /api/v1/curation/chain 엔드포인트
- [ ] GET /api/v1/curation/chain/{id} 엔드포인트
- [ ] 라우터 등록

**파일 목록**:
```
backend/app/api/v1_new/curation.py
backend/app/api/v1_new/__init__.py
```

**예상 시간**: 1시간
**의존성**: CP-2.2

---

### CP-4.2: AI 체인 생성 로직
- [ ] `backend/app/core/chain/generator.py` 작성
- [ ] Person Story 생성 로직
- [ ] Place Story 생성 로직
- [ ] Era Story 생성 로직
- [ ] Causal Chain 생성 로직

**파일 목록**:
```
backend/app/core/chain/__init__.py
backend/app/core/chain/generator.py
```

**예상 시간**: 3시간
**의존성**: CP-4.1

---

## Phase 5: 프론트엔드 (선택적)

### CP-5.1: Chain View 컴포넌트
- [ ] `frontend/src/components/chain/` 디렉토리 생성
- [ ] ChainView.tsx 메인 컴포넌트
- [ ] PersonStoryView.tsx
- [ ] PlaceStoryView.tsx
- [ ] ChainTimeline.tsx

**예상 시간**: 4시간
**의존성**: CP-4.2

---

## 체크포인트 요약

| ID | 작업 | 상태 | 완료일 |
|----|------|------|--------|
| **Phase 1: 데이터 모델 확장** ||||
| CP-1.1 | V1 디렉토리 구조 | ✅ | 2026-01-01 |
| CP-1.2 | Period 모델 | ✅ | 2026-01-01 |
| CP-1.3 | Location 확장 | ✅ | 2026-01-01 |
| CP-1.4 | Event 확장 | ✅ | 2026-01-01 |
| CP-1.5 | Phase 1 마이그레이션 | ✅ | 2026-01-07 |
| **Phase 2: V1 스키마 재설계** ||||
| CP-2.1 | Polity 모델 | ✅ | 2026-01-07 |
| CP-2.2 | HistoricalChain 모델 | ✅ | 2026-01-07 |
| CP-2.3 | TextMention/EntityAlias 모델 | ✅ | 2026-01-07 |
| CP-2.4 | Person/Source 확장 | ✅ | 2026-01-07 |
| CP-2.5 | Associations 확장 | ✅ | 2026-01-07 |
| CP-2.6 | Alembic 마이그레이션 | ✅ | 2026-01-07 |
| CP-2.7 | 인덱스 최적화 | ✅ | 2026-01-07 |
| **Phase 3: 서비스 레이어** ||||
| CP-3.1 | Chain 서비스 | ⬜ | - |
| CP-3.2 | NER 파이프라인 | ⬜ | - |
| **Phase 4: 큐레이션 API** ||||
| CP-4.1 | 큐레이션 엔드포인트 | ⬜ | - |
| CP-4.2 | AI 체인 생성 로직 | ⬜ | - |
| **Phase 5: 프론트엔드** ||||
| CP-5.1 | Chain View 컴포넌트 | ⬜ | - |

**Phase 1-2 완료**: 12/12 체크포인트
**전체 진행률**: 12/17 (71%)

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-01 | V1 작업 계획 초안 작성 |
| 2026-01-07 | Phase 2 대규모 업데이트: V1 스키마 재설계 (Batch NER 5.65M 엔티티 대응) |
| 2026-01-07 | CP-1.5, CP-2.1~2.7 완료: Polity, HistoricalChain, TextMention 모델 + 마이그레이션 |
