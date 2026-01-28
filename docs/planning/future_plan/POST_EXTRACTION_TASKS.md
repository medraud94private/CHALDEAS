# Kiwix 추출 완료 후 작업 순서

## 현재 진행 상황

```
Kiwix 추출: 100% 완료! (19.3M / 19.3M)
├── persons:   126,807
├── locations: 528,080
└── events:    267,364  ← 11.9배 증가 (22,438 → 267,364)

소스 링크: 진행 중
├── persons:   미시작
├── locations: 미시작
└── events:    미시작
```

---

## 작업 순서 (의존성 고려)

### Phase A: 소스 기반 엔티티 링크 (기존 스키마)

**목표**: Wikipedia 추출 데이터를 기존 DB와 연결

```bash
# 1. Persons 링크
python poc/scripts/link_wikipedia_to_db.py --type persons --resume

# 2. Locations 링크
python poc/scripts/link_wikipedia_to_db.py --type locations --resume

# 3. Events 링크
python poc/scripts/link_wikipedia_to_db.py --type events --resume
```

**9가지 관계 매트릭스:**
```
           Person    Location    Event
Person     P↔P       P↔L         P↔E
Location   L↔P       L↔L         L↔E
Event      E↔P       E↔L         E↔E
```

**예상 시간**: 수 시간 (DB 작업)

---

### Phase B: DB 마이그레이션 (스키마 변경)

**순서가 중요함!**

#### B-1: Location 계층화

```sql
-- locations 테이블 확장
ALTER TABLE locations ADD COLUMN location_type VARCHAR(20);
ALTER TABLE locations ADD COLUMN parent_id INTEGER;
ALTER TABLE locations ADD COLUMN display_zoom_min FLOAT;
ALTER TABLE locations ADD COLUMN display_zoom_max FLOAT;

-- event_locations 연결 테이블
CREATE TABLE event_locations (...);
```

문서: `docs/planning/HIERARCHICAL_LOCATION_SYSTEM.md`

#### B-2: Historical Unit 통합

```sql
-- events + periods → historical_units
CREATE TABLE historical_units (...);
CREATE TABLE historical_unit_locations (...);
CREATE TABLE historical_unit_relations (...);

-- 데이터 마이그레이션
INSERT INTO historical_units SELECT ... FROM events;
INSERT INTO historical_units SELECT ... FROM periods;
```

문서: `docs/planning/UNIFIED_HISTORICAL_UNIT.md`

#### B-3: 날짜 정밀도 확장

```sql
-- historical_units에 정밀 날짜 추가
ALTER TABLE historical_units ADD COLUMN date_start DATE;
ALTER TABLE historical_units ADD COLUMN date_start_precision VARCHAR(20);
ALTER TABLE historical_units ADD COLUMN date_start_is_bce BOOLEAN;
-- ... (end도 동일)
```

문서: `docs/planning/WIKIDATA_AUTO_ENRICHMENT.md`

---

### Phase C: Wikidata 자동 보강

**QID 있는 엔티티들 일괄 보강**

```bash
# 1. 날짜 정밀도 보강
python poc/scripts/wikidata_enrich_dates.py --batch 500 --resume

# 2. 시대 자동 연결
python poc/scripts/wikidata_link_periods.py --method hybrid --resume

# 3. 계층 구조 구축
python poc/scripts/wikidata_build_hierarchy.py --resume
```

---

### Phase D: Period/Era 추출 (추가 데이터)

```bash
# kiwix_extract_all.py 확장 후 재실행
python poc/scripts/kiwix_extract_all.py --type period --resume
python poc/scripts/kiwix_extract_all.py --type polity --resume
```

문서: `docs/planning/PERIOD_EXTRACTION_PLAN.md`

---

### Phase E: API/Frontend 전환

```python
# 1. API 라우터 업데이트
# /events, /periods → /units 통합

# 2. Frontend 컴포넌트 업데이트
# - GlobeContainer: scale 기반 필터링
# - Timeline: 계층 드릴다운

# 3. 하위 호환성 유지
# - /events, /periods 요청 → /units로 리다이렉트
```

---

## 체크리스트

### Phase A: 소스 링크
- [ ] persons 링크 완료
- [ ] locations 링크 완료
- [ ] events 링크 완료
- [ ] 9가지 관계 검증

### Phase B: DB 마이그레이션
- [ ] B-1: Location 계층화
- [ ] B-2: Historical Unit 통합
- [ ] B-3: 날짜 정밀도 확장
- [ ] 기존 데이터 마이그레이션 검증

### Phase C: Wikidata 보강
- [ ] 날짜 정밀도 보강
- [ ] 시대 자동 연결
- [ ] 계층 구조 구축

### Phase D: 추가 추출
- [ ] Period 추출
- [ ] Polity 추출
- [ ] DB 임포트

### Phase E: API/Frontend
- [ ] /units API 생성
- [ ] Globe scale 필터링
- [ ] 하위 호환성

---

## 예상 일정

| Phase | 작업 | 자동화 | 예상 |
|-------|------|--------|------|
| A | 소스 링크 | 스크립트 | 수 시간 |
| B-1 | Location 계층 | Alembic | 30분 |
| B-2 | Historical Unit | Alembic + Script | 1시간 |
| B-3 | 날짜 정밀도 | Alembic | 15분 |
| C | Wikidata 보강 | 스크립트 | 수 시간 (API 제한) |
| D | 추가 추출 | 스크립트 | 수 시간 |
| E | API/Frontend | 수동 | 반나절 |

---

## 의존성 그래프

```
Kiwix 추출 완료
       │
       ▼
   Phase A: 소스 링크 ─────────────────┐
       │                              │
       ▼                              │
   Phase B-1: Location 계층화         │
       │                              │
       ▼                              │
   Phase B-2: Historical Unit 통합 ◄──┘
       │
       ├──► Phase B-3: 날짜 정밀도
       │
       ▼
   Phase C: Wikidata 보강
       │
       ├──► Phase D: 추가 추출 (병렬 가능)
       │
       ▼
   Phase E: API/Frontend
```

---

## 롤백 계획

각 Phase는 독립적으로 롤백 가능:
- Alembic: `alembic downgrade -1`
- 데이터: 마이그레이션 전 pg_dump 백업
- 스크립트: 체크포인트 기반 재시작
