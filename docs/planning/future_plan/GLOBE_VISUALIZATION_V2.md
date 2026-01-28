# Globe Visualization V2 계획

> 작성일: 2026-01-12
> 상태: 계획 단계

---

## 현재 시스템의 한계

### 1. 단일 좌표만 지원
```
현재: Event → 하나의 (lat, lng) 좌표
문제: "백년전쟁"은 프랑스 전역에서 일어난 사건
```

### 2. 시간 흐름 미지원
```
현재: Event.date_start ~ date_end (정적 범위)
문제: 1337년 시작 → 1360년 브레티니 조약 → 1415년 아쟁쿠르 → 1453년 종료
      각 단계별 지역 변화를 보여줄 수 없음
```

### 3. 역할 구분 미지원
```
현재: 단순히 "이벤트 발생 위치"
문제: 공격측(잉글랜드) vs 수비측(프랑스)
      점령 지역 변화, 전투 결과 등 시각화 불가
```

---

## V2 목표

**"지역 기반 + 시간 흐름 + 다중 관점"** 이벤트 시각화

### 예시: 백년전쟁 (1337-1453)

```
[1337년] 전쟁 시작
  - 잉글랜드 영토: 보르도, 아키텐 (파란색 폴리곤)
  - 프랑스 영토: 나머지 (빨간색 폴리곤)

[1360년] 브레티니 조약
  - 잉글랜드 영토 확대 (애니메이션으로 변화 표시)
  - 주요 전투 마커: 크레시, 푸아티에

[1415년] 아쟁쿠르 전투
  - 전투 위치 마커 + 화살표 (공격 방향)
  - 결과: 잉글랜드 승리

[1429년] 잔 다르크
  - 오를레앙 → 랭스 진군 경로 (arc로 표시)
  - 프랑스 영토 회복 시작

[1453년] 전쟁 종료
  - 칼레만 잉글랜드 영토로 남음
```

---

## 데이터 모델 설계

### Option A: Event 확장

```sql
-- 기존 events 테이블에 컬럼 추가
ALTER TABLE events ADD COLUMN geo_type VARCHAR(20) DEFAULT 'point';
-- 'point' | 'polygon' | 'multi_point' | 'path'

ALTER TABLE events ADD COLUMN geo_data JSONB;
-- polygon: {"type": "Polygon", "coordinates": [...]}
-- path: {"type": "LineString", "coordinates": [...], "direction": "forward"}

ALTER TABLE events ADD COLUMN phases JSONB;
-- 시간에 따른 단계 정보
-- [{"year": 1337, "title": "War begins", "geo_change": {...}}, ...]
```

### Option B: 별도 테이블 (권장)

```sql
-- 이벤트의 지리적 범위
CREATE TABLE event_regions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    region_type VARCHAR(20),  -- 'territory', 'battle_area', 'route'
    geo_data GEOMETRY,        -- PostGIS geometry
    role VARCHAR(50),         -- 'attacker', 'defender', 'neutral'
    faction VARCHAR(100),     -- 'England', 'France'
    year_start INTEGER,
    year_end INTEGER,
    properties JSONB          -- 추가 속성
);

-- 이벤트의 시간별 단계
CREATE TABLE event_phases (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    phase_order INTEGER,
    year INTEGER,
    title VARCHAR(255),
    description TEXT,
    geo_changes JSONB,        -- 지역 변화 정보
    key_events JSONB          -- 해당 단계의 주요 사건들
);

-- 이벤트 간 이동/진군 경로
CREATE TABLE event_movements (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    movement_type VARCHAR(50), -- 'march', 'retreat', 'trade_route', 'migration'
    path_data GEOMETRY,        -- PostGIS LineString
    direction VARCHAR(20),     -- 'forward', 'backward', 'bidirectional'
    year INTEGER,
    faction VARCHAR(100),
    description TEXT
);
```

---

## API 설계

### 1. 지역 기반 이벤트 조회

```
GET /api/v2/events/{event_id}/regions
```

```json
{
  "event_id": 12345,
  "title": "Hundred Years' War",
  "regions": [
    {
      "id": 1,
      "role": "attacker",
      "faction": "England",
      "geo_type": "polygon",
      "geo_data": { "type": "Polygon", "coordinates": [...] },
      "year_start": 1337,
      "year_end": 1453,
      "color": "#3b82f6"
    },
    {
      "id": 2,
      "role": "defender",
      "faction": "France",
      "geo_type": "polygon",
      "geo_data": { "type": "Polygon", "coordinates": [...] },
      "year_start": 1337,
      "year_end": 1453,
      "color": "#ef4444"
    }
  ]
}
```

### 2. 시간별 단계 조회

```
GET /api/v2/events/{event_id}/phases
```

```json
{
  "event_id": 12345,
  "phases": [
    {
      "phase_order": 1,
      "year": 1337,
      "title": "War Begins",
      "description": "Edward III claims French throne",
      "territory_changes": [
        { "faction": "England", "action": "claim", "regions": [...] }
      ],
      "key_battles": []
    },
    {
      "phase_order": 2,
      "year": 1346,
      "title": "Battle of Crécy",
      "description": "English longbowmen defeat French cavalry",
      "battle_location": { "lat": 50.26, "lng": 1.88 },
      "result": "English victory"
    }
  ]
}
```

### 3. 진군/이동 경로 조회

```
GET /api/v2/events/{event_id}/movements
```

```json
{
  "event_id": 12345,
  "movements": [
    {
      "id": 1,
      "type": "march",
      "faction": "France",
      "leader": "Joan of Arc",
      "year": 1429,
      "path": {
        "type": "LineString",
        "coordinates": [
          [1.9, 47.9],   // Orléans
          [2.35, 48.86], // Paris area
          [4.03, 49.25]  // Reims
        ]
      },
      "description": "Joan's march to Reims for coronation"
    }
  ]
}
```

---

## 프론트엔드 시각화

### 1. 폴리곤 레이어 (영토/지역)

```typescript
// react-globe.gl 폴리곤 지원
<Globe
  polygonsData={eventRegions}
  polygonGeoJsonGeometry={(d) => d.geo_data}
  polygonCapColor={(d) => d.color + '80'}  // 반투명
  polygonSideColor={(d) => d.color + '40'}
  polygonStrokeColor={(d) => d.color}
  polygonLabel={(d) => `${d.faction} territory (${d.year_start})`}
/>
```

### 2. 시간 슬라이더 연동

```typescript
// 타임라인 연도에 따라 폴리곤 필터링
const visibleRegions = useMemo(() => {
  return eventRegions.filter(r =>
    currentYear >= r.year_start &&
    currentYear <= r.year_end
  )
}, [eventRegions, currentYear])
```

### 3. 애니메이션 경로 (진군 루트)

```typescript
// arcsData로 이동 경로 표시
<Globe
  arcsData={movements}
  arcStartLat={(d) => d.path.coordinates[0][1]}
  arcStartLng={(d) => d.path.coordinates[0][0]}
  arcEndLat={(d) => d.path.coordinates.at(-1)[1]}
  arcEndLng={(d) => d.path.coordinates.at(-1)[0]}
  arcDashLength={0.4}
  arcDashGap={0.2}
  arcDashAnimateTime={2000}  // 애니메이션
  arcColor={(d) => d.faction_color}
/>
```

### 4. 전투 마커 (특수 스타일)

```typescript
// 전투는 특별한 마커로 표시
const battleMarkers = phases
  .filter(p => p.battle_location)
  .map(p => ({
    ...p.battle_location,
    type: 'battle',
    result: p.result,
    icon: '⚔️'
  }))
```

---

## 구현 로드맵

### Phase 1: 데이터 모델 (2주)
- [ ] `event_regions` 테이블 생성
- [ ] `event_phases` 테이블 생성
- [ ] `event_movements` 테이블 생성
- [ ] 기본 CRUD API 구현

### Phase 2: 샘플 데이터 (1주)
- [ ] 백년전쟁 데이터 입력
- [ ] 알렉산더 대왕 원정 데이터 입력
- [ ] 로마 제국 확장 데이터 입력

### Phase 3: 폴리곤 시각화 (2주)
- [ ] Globe에 폴리곤 레이어 추가
- [ ] 영토 색상/투명도 처리
- [ ] 연도별 필터링

### Phase 4: 애니메이션 (2주)
- [ ] 진군 경로 아크 표시
- [ ] 시간에 따른 영토 변화 애니메이션
- [ ] 전투 마커 특수 효과

### Phase 5: UI/UX (1주)
- [ ] 이벤트 상세 패널에 "단계별 보기" 탭 추가
- [ ] 타임라인과 연동
- [ ] 범례 (공격/수비 색상 설명)

---

## 데이터 소스

### 지리 데이터
- **Natural Earth**: 국경선, 지역 폴리곤
- **GADM**: 행정구역 경계
- **OpenStreetMap**: 도시, 전투지 위치

### 역사 데이터
- **Wikipedia**: 전쟁 타임라인, 영토 변화
- **Britannica**: 상세 설명
- **학술 자료**: 지도 재구성

---

## 기술적 고려사항

### PostGIS 사용
```sql
-- PostGIS 확장 활성화
CREATE EXTENSION IF NOT EXISTS postgis;

-- 공간 쿼리 예시: 특정 지점이 어느 영토에 속하는지
SELECT er.faction, er.year_start, er.year_end
FROM event_regions er
WHERE ST_Contains(er.geo_data, ST_Point(2.35, 48.86))
  AND er.event_id = 12345
  AND 1429 BETWEEN er.year_start AND er.year_end;
```

### 성능 최적화
- 폴리곤 단순화 (ST_Simplify) - 줌 레벨에 따라
- 타일 기반 로딩 (대규모 데이터)
- 캐싱 전략

---

## 예상 효과

1. **백년전쟁** - 프랑스 전역의 영토 변화를 시간순으로 시각화
2. **몽골 제국 확장** - 칭기즈칸 원정 경로와 영토 확장
3. **로마 제국** - BCE 753 ~ CE 476 영토 변화
4. **알렉산더 원정** - 마케도니아 → 페르시아 → 인도 진군 경로
5. **십자군 전쟁** - 유럽 → 예루살렘 이동 경로

---

## 관련 문서

- `docs/planning/HISTORICAL_CHAIN_CONCEPT.md` - 역사의 고리 컨셉
- `docs/implemented/DATABASE.md` - 현재 DB 스키마
- `docs/planning/DATA_PIPELINE_V2.md` - 데이터 파이프라인
