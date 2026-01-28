# Road to V3 - 시스템 재설계 로드맵

## 개요

CHALDEAS V3는 다음을 목표로 함:
1. **통합 데이터 모델**: Event + Period → HistoricalUnit
2. **계층적 공간 구조**: Location hierarchy (city → region → empire)
3. **유연한 시간 표현**: 날짜 정밀도 (day/month/year/century/circa)
4. **자동화된 데이터 파이프라인**: Wikidata 보강, 신규 데이터 진입

---

## 문서 목록

| 문서 | 설명 | 상태 |
|------|------|------|
| [POST_EXTRACTION_TASKS.md](./POST_EXTRACTION_TASKS.md) | 전체 작업 순서 및 체크리스트 | 마스터 플랜 |
| [UNIFIED_HISTORICAL_UNIT.md](./UNIFIED_HISTORICAL_UNIT.md) | Event/Period 통합 모델 | 설계 완료 |
| [HIERARCHICAL_LOCATION_SYSTEM.md](./HIERARCHICAL_LOCATION_SYSTEM.md) | 장소 계층 구조 | 설계 완료 |
| [WIKIDATA_AUTO_ENRICHMENT.md](./WIKIDATA_AUTO_ENRICHMENT.md) | Wikidata 자동 보강 | 설계 완료 |
| [PERIOD_EXTRACTION_PLAN.md](./PERIOD_EXTRACTION_PLAN.md) | 시대/기간 추출 | 설계 완료 |
| [DATA_INGESTION_PIPELINE.md](./DATA_INGESTION_PIPELINE.md) | V3 완성 후 데이터 진입 경로 | 설계 완료 |
| [MULTIVERSE_DATA_MODEL.md](./MULTIVERSE_DATA_MODEL.md) | 역사+창작물 통합 관리 (Universe) | 설계 완료 |
| [CURATION_SYSTEM.md](./CURATION_SYSTEM.md) | AI 큐레이터, 스토리 콘텐츠, 페르소나 | 설계 완료 |
| [SYSTEM_GAPS_AND_SOLUTIONS.md](./SYSTEM_GAPS_AND_SOLUTIONS.md) | 검색, 성능, 품질관리, 운영도구 | 보완 계획 |

---

## 아키텍처 변화

### Before (V2)
```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ events  │  │ periods │  │ persons │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └─────┬──────┘            │
           │                   │
     event_periods        person_events
```

### After (V3)
```
┌─────────────────────┐  ┌─────────┐  ┌──────────┐
│  historical_units   │  │ persons │  │ polities │
│  (event+period)     │  └────┬────┘  └────┬─────┘
│  - unit_type        │       │            │
│  - scale            │       │            │
│  - parent_id        │       │            │
└──────────┬──────────┘       │            │
           │                  │            │
           ├──────────────────┴────────────┘
           │
    ┌──────┴───────┐
    │  locations   │
    │  (hierarchy) │
    │  - parent_id │
    │  - type      │
    └──────────────┘
```

---

## 데이터 모델 핵심 변경

### 1. HistoricalUnit (통합)

```sql
historical_units
├── id, name, slug
├── unit_type: battle/war/treaty/period/era/movement/...
├── scale: evenementielle/conjuncture/longue_duree
├── parent_id → 계층 (백년전쟁 → 크레시 전투)
├── date_start, date_end + precision
├── scope_type: point/region/multi_region
└── wikidata_id
```

### 2. Location (계층화)

```sql
locations
├── id, name
├── location_type: city/region/country/empire/cultural_sphere
├── parent_id → 계층 (Rome → Italia → Roman Empire)
├── latitude, longitude
└── display_zoom_min, display_zoom_max
```

### 3. 관계 테이블

```sql
historical_unit_locations (unit ↔ location)
historical_unit_relations (unit ↔ unit: causes, part_of, ...)
person_units (person ↔ unit)
polity_units (polity ↔ unit)
```

---

## 실행 순서

```
Phase A: 소스 링크 (기존 스키마에서)
    ↓
Phase B: DB 마이그레이션
    ├── B-1: Location 계층화
    ├── B-2: HistoricalUnit 통합
    └── B-3: 날짜 정밀도
    ↓
Phase C: Wikidata 자동 보강
    ├── 날짜 정밀도
    ├── 시대 연결
    └── 계층 구조
    ↓
Phase D: 추가 데이터 추출
    ├── Period 추출
    └── Polity 추출
    ↓
Phase E: API/Frontend 전환
    ├── /units API
    ├── Globe scale 필터링
    └── 계층 드릴다운 UI
    ↓
Phase F: 데이터 진입 파이프라인
    ├── Wikipedia 업데이트
    ├── Wikidata 업데이트
    ├── 사용자 제출
    └── 관리자 도구
    ↓
Phase G: 큐레이션 시스템
    ├── Curator AI 파이프라인
    ├── 페르소나 (official/mash/leonardo)
    ├── Story 콘텐츠 생성
    └── 1차 사료 연결
    ↓
Phase H: 운영 인프라
    ├── 검색 시스템 V3 (scale/universe 필터)
    ├── 성능 최적화 (캐싱, LOD)
    ├── 데이터 품질 관리
    └── 관리자 대시보드
```

---

## 데이터 진입 경로 (V3 완성 후)

```
┌──────────────────────────────────────────────────┐
│               Data Entry Points                   │
├──────────────────────────────────────────────────┤
│                                                  │
│  Wikipedia ──┬──► Ingestion Pipeline ──► DB     │
│  Wikidata  ──┤         │                        │
│  User      ──┤         ├── Validate             │
│  Admin     ──┘         ├── Classify             │
│                        ├── Enrich (Wikidata)    │
│                        └── Link (periods, locs) │
│                                                  │
└──────────────────────────────────────────────────┘
```

**4가지 진입 경로:**
1. **Wikipedia**: 정기 덤프 업데이트 / 실시간 스트림
2. **Wikidata**: QID 기반 변경 감지 / 신규 발견
3. **User**: 웹 UI 제출 → 검토 → 승인
4. **Admin**: 수동 추가 / 일괄 임포트

---

## 의존성

### 선행 작업
- [x] Kiwix Wikipedia 추출 (진행 중, 78%)
- [ ] 소스 기반 엔티티 링크

### V3 마이그레이션
- [ ] Alembic 마이그레이션 스크립트
- [ ] 데이터 변환 스크립트
- [ ] API 라우터 업데이트
- [ ] Frontend 컴포넌트 업데이트

### V3 운영
- [ ] 데이터 진입 파이프라인 구현
- [ ] 관리자 대시보드
- [ ] 모니터링/알림

---

## 예상 타임라인

```
Week 1: Phase A (소스 링크)
Week 2: Phase B (DB 마이그레이션)
Week 3: Phase C + D (Wikidata 보강 + 추가 추출)
Week 4: Phase E (API/Frontend)
Week 5: Phase F (진입 파이프라인)
Week 6: Phase G (큐레이션 시스템)
Week 7+: Phase H (운영 인프라)
```

---

## 성공 지표

| 지표 | 목표 |
|------|------|
| HistoricalUnit 수 | 50,000+ |
| Period 연결률 | 80%+ |
| Location 계층 커버리지 | 90%+ |
| Wikidata 매칭률 | 60%+ |
| 날짜 정밀도 (day/month) | 30%+ |
| Story 콘텐츠 (주요 인물) | 100명+ |
| 1차 사료 연결률 | 70%+ |
| 검색 응답 시간 | < 200ms |
| Globe 렌더링 FPS | 60fps |
| 데이터 품질 점수 평균 | 70%+ |
