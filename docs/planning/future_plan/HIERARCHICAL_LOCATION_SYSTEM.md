# Hierarchical Location System 설계

## 개요

이벤트의 직접 좌표 지정 방식에서 Location 엔티티 기반 구조로 전환.
다지역 이벤트 지원 및 줌 레벨별 계층적 표시 구현.

## 현재 문제점

1. **중복 좌표**: 같은 장소(로마)가 여러 이벤트에 각각 좌표로 저장됨
2. **일관성 없음**: 어떤 이벤트는 location_id, 어떤 건 직접 좌표
3. **다지역 불가**: "포에니 전쟁"처럼 여러 지역에 걸친 이벤트 표현 어려움
4. **계층 없음**: 로마 → 이탈리아 → 로마제국 관계 표현 불가

---

## 새 스키마 설계

### 1. Location 테이블 확장

```sql
ALTER TABLE locations ADD COLUMN location_type VARCHAR(20);
-- city, region, country, empire, cultural_sphere, sea, continent

ALTER TABLE locations ADD COLUMN parent_id INTEGER REFERENCES locations(id);

ALTER TABLE locations ADD COLUMN boundary_geojson JSONB;
-- 선택: 영역 다각형 (지도에 영역 표시용)

ALTER TABLE locations ADD COLUMN display_zoom_min FLOAT DEFAULT 0;
ALTER TABLE locations ADD COLUMN display_zoom_max FLOAT DEFAULT 10;
-- 줌 레벨별 표시 제어
```

### 2. EventLocation 연결 테이블 (신규 또는 확장)

```sql
CREATE TABLE event_locations (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    role VARCHAR(20) DEFAULT 'primary',
    -- primary: 주요 발생지
    -- secondary: 부차적 장소
    -- origin: 출발지 (이동/원정)
    -- destination: 도착지
    -- affected: 영향받은 지역
    sequence_order INTEGER DEFAULT 0,
    -- 이동 이벤트의 경우 순서
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(event_id, location_id, role)
);

CREATE INDEX idx_event_locations_event ON event_locations(event_id);
CREATE INDEX idx_event_locations_location ON event_locations(location_id);
```

### 3. Location 계층 예시

```
Mediterranean (cultural_sphere)
├── Roman Empire (empire)
│   ├── Italia (region)
│   │   ├── Rome (city)
│   │   ├── Pompeii (city)
│   │   └── Naples (city)
│   ├── Hispania (region)
│   │   └── Carthago Nova (city)
│   └── Aegyptus (region)
│       └── Alexandria (city)
├── Carthaginian Empire (empire)
│   ├── North Africa (region)
│   │   ├── Carthage (city)
│   │   └── Utica (city)
│   └── Western Sicily (region)
└── Hellenic World (empire/cultural_sphere)
    ├── Attica (region)
    │   └── Athens (city)
    └── Peloponnese (region)
        └── Sparta (city)
```

---

## 마이그레이션 계획

### Phase 1: 스키마 확장 (비파괴적)

```sql
-- 1. 새 컬럼 추가 (기존 데이터 영향 없음)
ALTER TABLE locations ADD COLUMN location_type VARCHAR(20) DEFAULT 'city';
ALTER TABLE locations ADD COLUMN parent_id INTEGER REFERENCES locations(id);
ALTER TABLE locations ADD COLUMN display_zoom_min FLOAT DEFAULT 0;
ALTER TABLE locations ADD COLUMN display_zoom_max FLOAT DEFAULT 4;

-- 2. event_locations 테이블 생성
CREATE TABLE IF NOT EXISTS event_locations (...);
```

### Phase 2: 데이터 마이그레이션

```python
# 1. 기존 이벤트의 직접 좌표 → Location 매칭
for event in events_with_coords:
    # 가장 가까운 기존 Location 찾기
    location = find_nearest_location(event.latitude, event.longitude)
    if location and distance < 50km:
        create_event_location(event.id, location.id, 'primary')
    else:
        # 새 Location 생성
        new_loc = create_location(name=event.location_name, lat=event.lat, lng=event.lng)
        create_event_location(event.id, new_loc.id, 'primary')

# 2. 지역 계층 구조 생성
create_region_hierarchy_from_wikidata()
```

### Phase 3: API/Frontend 수정

```python
# events.py - Location 기반 좌표 조회
@router.get("/events")
def get_events():
    # 기존: event.latitude, event.longitude
    # 신규: event.locations[0].latitude (primary location)
    pass
```

### Phase 4: 이벤트 직접 좌표 필드 Deprecate

```sql
-- 충분한 검증 후
ALTER TABLE events DROP COLUMN latitude;
ALTER TABLE events DROP COLUMN longitude;
```

---

## 줌 레벨별 표시 로직

```typescript
// GlobeContainer.tsx
const getDisplayLocations = (locations: Location[], altitude: number) => {
  return locations.filter(loc => {
    // 줌 레벨에 맞는 location_type만 표시
    if (altitude > 3.0) {
      return ['cultural_sphere', 'empire', 'continent'].includes(loc.location_type)
    } else if (altitude > 1.5) {
      return ['empire', 'country', 'region'].includes(loc.location_type)
    } else {
      return ['city', 'region'].includes(loc.location_type)
    }
  })
}

// 이벤트 표시 시
const getEventDisplayLocation = (event: Event, altitude: number) => {
  // 현재 줌 레벨에 맞는 가장 적절한 location 선택
  const primaryLoc = event.locations.find(l => l.role === 'primary')
  return findAppropriateAncestor(primaryLoc, altitude)
}
```

---

## 다지역 이벤트 처리

### 예시: 포에니 전쟁 (264-146 BC)

```json
{
  "event": "Second Punic War",
  "locations": [
    { "location": "Carthage", "role": "origin" },
    { "location": "Hispania", "role": "secondary" },
    { "location": "Alps", "role": "secondary", "sequence": 1 },
    { "location": "Italia", "role": "destination", "sequence": 2 },
    { "location": "Cannae", "role": "primary" },
    { "location": "Zama", "role": "primary" }
  ]
}
```

### Globe 표시 옵션

1. **Primary만 표시**: 주요 전투 장소만 마커
2. **영역 표시**: 관련 region들을 반투명 영역으로 표시
3. **경로 표시**: origin → destination 아크 그리기 (한니발 진군로)

---

## 예상 작업량

| Phase | 작업 | 예상 |
|-------|------|------|
| 1 | 스키마 확장 | Alembic migration 1개 |
| 2 | 데이터 마이그레이션 스크립트 | Python script |
| 3 | API 수정 (events, locations) | Backend 수정 |
| 4 | Globe 컴포넌트 수정 | Frontend 수정 |
| 5 | 계층 데이터 수집 (Wikidata) | POC script |

---

## 의존성

- [ ] Kiwix 추출 완료 (현재 진행 중)
- [ ] 기존 Location 데이터 품질 확인
- [ ] Wikidata에서 지역 계층 정보 수집 가능 여부 확인

---

## 참고: Wikidata 계층 쿼리

```sparql
# 로마의 상위 행정구역 조회
SELECT ?place ?placeLabel ?parent ?parentLabel WHERE {
  wd:Q220 wdt:P131* ?place .  # Q220 = Rome
  ?place wdt:P131 ?parent .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

이 쿼리로 City → Region → Country → Empire 계층 자동 구축 가능.
