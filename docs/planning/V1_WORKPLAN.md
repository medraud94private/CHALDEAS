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

### CP-1.5: Alembic 마이그레이션 생성
- [ ] `periods` 테이블 마이그레이션
- [ ] `locations` 확장 마이그레이션
- [ ] `events` 확장 마이그레이션
- [ ] 마이그레이션 테스트 (로컬 DB)

**파일 목록**:
```
backend/alembic/versions/xxxx_add_v1_models.py
```

**예상 시간**: 30분
**의존성**: CP-1.2, CP-1.3, CP-1.4

---

## Phase 2: HistoricalChain 시스템

### CP-2.1: HistoricalChain 모델 생성
- [ ] `backend/app/models/v1/chain.py` 작성
- [ ] HistoricalChain 모델 정의
- [ ] ChainSegment 모델 정의
- [ ] 관계 설정 (Person, Location, Period, Event)

**파일 목록**:
```
backend/app/models/v1/chain.py
backend/app/schemas/v1/chain.py
```

**예상 시간**: 45분
**의존성**: CP-1.5

---

### CP-2.2: Chain 서비스 레이어
- [ ] `backend/app/services/chain_service.py` 작성
- [ ] 체인 생성 로직
- [ ] 승격 로직 (user → cached → featured → system)
- [ ] 캐시 조회 로직

**파일 목록**:
```
backend/app/services/chain_service.py
```

**예상 시간**: 1시간
**의존성**: CP-2.1

---

### CP-2.3: Chain 마이그레이션
- [ ] `historical_chains` 테이블 마이그레이션
- [ ] `chain_segments` 테이블 마이그레이션
- [ ] 인덱스 추가
- [ ] 마이그레이션 테스트

**파일 목록**:
```
backend/alembic/versions/xxxx_add_chain_tables.py
```

**예상 시간**: 20분
**의존성**: CP-2.1

---

## Phase 3: 텍스트-엔티티 연결

### CP-3.1: TextSource/TextMention 모델
- [ ] `backend/app/models/v1/text_mention.py` 작성
- [ ] TextSource 모델 정의
- [ ] TextMention 모델 정의
- [ ] 스키마 작성

**파일 목록**:
```
backend/app/models/v1/text_mention.py
backend/app/schemas/v1/text_mention.py
```

**예상 시간**: 30분
**의존성**: CP-1.5

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

**예상 시간**: 2시간
**의존성**: CP-3.1

---

### CP-3.3: Text 마이그레이션
- [ ] `text_sources` 테이블 마이그레이션
- [ ] `text_mentions` 테이블 마이그레이션
- [ ] 인덱스 추가

**파일 목록**:
```
backend/alembic/versions/xxxx_add_text_tables.py
```

**예상 시간**: 15분
**의존성**: CP-3.1

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

| ID | 작업 | 예상 시간 | 상태 |
|----|------|----------|------|
| CP-1.1 | V1 디렉토리 구조 | 5분 | ✅ |
| CP-1.2 | Period 모델 | 30분 | ✅ |
| CP-1.3 | Location 확장 | 20분 | ✅ |
| CP-1.4 | Event 확장 | 15분 | ✅ |
| CP-1.5 | Phase 1 마이그레이션 | 30분 | ⬜ |
| CP-2.1 | Chain 모델 | 45분 | ⬜ |
| CP-2.2 | Chain 서비스 | 1시간 | ⬜ |
| CP-2.3 | Chain 마이그레이션 | 20분 | ⬜ |
| CP-3.1 | Text 모델 | 30분 | ⬜ |
| CP-3.2 | NER 파이프라인 | 2시간 | ⬜ |
| CP-3.3 | Text 마이그레이션 | 15분 | ⬜ |
| CP-4.1 | 큐레이션 API | 1시간 | ⬜ |
| CP-4.2 | AI 체인 생성 | 3시간 | ⬜ |
| CP-5.1 | 프론트엔드 | 4시간 | ⬜ |

**총 예상 시간**: ~14시간

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-01 | V1 작업 계획 초안 작성 |
