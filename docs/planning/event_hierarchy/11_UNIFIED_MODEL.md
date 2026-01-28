# Unified Historical Unit 설계

## 개요

Event, Period를 하나의 `HistoricalUnit`으로 통합.
관리 주체를 줄이고, 시간-공간 범위를 일관되게 표현.

---

## 현재 문제점

```
현재 3개 테이블:
├── events      (전투, 조약, 사건)
├── periods     (시대, 기간)
└── polities    (제국, 왕국) ← 이건 "행위자"라 별도 유지

문제:
1. 백년전쟁: Event인가 Period인가?
2. 십자군 전쟁: 200년 걸친 Event?
3. 중복 필드: year_start, year_end 둘 다 있음
4. 관계 복잡: event_periods, period_events 등 연결 테이블 난립
```

---

## 통합 모델: HistoricalUnit

### 핵심 테이블

```sql
CREATE TABLE historical_units (
    id SERIAL PRIMARY KEY,

    -- 식별
    name VARCHAR(300) NOT NULL,
    name_ko VARCHAR(300),
    slug VARCHAR(300) UNIQUE NOT NULL,

    -- 시간 범위
    year_start INTEGER NOT NULL,
    year_start_precision VARCHAR(20) DEFAULT 'year',  -- exact, year, decade, century
    year_end INTEGER,
    year_end_precision VARCHAR(20) DEFAULT 'year',

    -- 분류
    unit_type VARCHAR(30) NOT NULL,
    -- 'battle', 'war', 'treaty', 'revolution', 'movement',
    -- 'period', 'era', 'age', 'dynasty_period',
    -- 'natural_event', 'cultural_event'

    scale VARCHAR(20) NOT NULL DEFAULT 'conjuncture',
    -- 'evenementielle': 단기 (일~년)
    -- 'conjuncture': 중기 (수년~수십년)
    -- 'longue_duree': 장기 (세기~천년)

    -- 계층 (백년전쟁 → 크레시 전투)
    parent_id INTEGER REFERENCES historical_units(id),
    sequence_order INTEGER DEFAULT 0,  -- 형제 간 순서

    -- 공간 범위
    scope_type VARCHAR(20) DEFAULT 'point',
    -- 'point': 단일 좌표 (전투)
    -- 'region': 지역 (로마 제국 영토 내)
    -- 'multi_region': 다지역 (백년전쟁: 프랑스, 영국, 플랑드르)
    -- 'global': 전세계 (세계대전)

    -- 확실성
    certainty VARCHAR(20) DEFAULT 'fact',
    -- 'fact', 'probable', 'legendary', 'mythological'

    -- 내용
    description TEXT,
    description_ko TEXT,
    summary VARCHAR(500),

    -- 메타
    importance INTEGER DEFAULT 5,  -- 1-10
    wikidata_id VARCHAR(20),
    wikipedia_url VARCHAR(500),
    image_url VARCHAR(500),

    -- 벡터 검색
    embedding VECTOR(1536),

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_hu_year ON historical_units(year_start, year_end);
CREATE INDEX idx_hu_type ON historical_units(unit_type);
CREATE INDEX idx_hu_scale ON historical_units(scale);
CREATE INDEX idx_hu_parent ON historical_units(parent_id);
CREATE INDEX idx_hu_wikidata ON historical_units(wikidata_id);
```

### 장소 연결 (다중 지역 지원)

```sql
CREATE TABLE historical_unit_locations (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL REFERENCES historical_units(id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL REFERENCES locations(id),

    role VARCHAR(30) DEFAULT 'primary',
    -- 'primary': 주 발생지
    -- 'secondary': 부차적 장소
    -- 'origin': 출발지/발원지
    -- 'destination': 도착지/목적지
    -- 'affected': 영향받은 지역

    sequence_order INTEGER DEFAULT 0,  -- 이동 순서

    UNIQUE(unit_id, location_id, role)
);
```

### 연관 관계 (인과, 영향)

```sql
CREATE TABLE historical_unit_relations (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES historical_units(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES historical_units(id) ON DELETE CASCADE,

    relation_type VARCHAR(30) NOT NULL,
    -- 'causes': 원인 → 결과
    -- 'leads_to': ~로 이어짐
    -- 'part_of': 포함 관계 (parent_id와 별개로 느슨한 연결)
    -- 'contemporary': 동시대
    -- 'influences': 영향
    -- 'responds_to': 대응/반응

    strength INTEGER DEFAULT 5,  -- 1-10
    description TEXT,

    UNIQUE(source_id, target_id, relation_type)
);
```

---

## 분류 체계

### unit_type 값

```
전쟁/갈등:
  - battle: 단일 전투 (세키가하라)
  - siege: 공성전 (콘스탄티노플 함락)
  - war: 전쟁 (임진왜란, 백년전쟁)
  - conquest: 정복 (알렉산더 정복)
  - revolution: 혁명 (프랑스 혁명)
  - rebellion: 반란 (황건적의 난)

정치/외교:
  - treaty: 조약 (베스트팔렌 조약)
  - coronation: 즉위/대관식
  - founding: 건국/설립
  - collapse: 멸망/붕괴

시대/기간:
  - period: 일반 시대 (헬레니즘 시대)
  - era: 큰 시대 (고대, 중세)
  - age: ~시대 (청동기 시대)
  - dynasty_period: 왕조 시기 (당나라 시대)
  - movement: 운동/사조 (르네상스, 계몽주의)

기타:
  - natural_event: 자연재해 (폼페이 화산)
  - cultural_event: 문화 이벤트 (올림픽 기원)
  - discovery: 발견 (신대륙 발견)
```

### scale 자동 판정

```python
def determine_scale(year_start: int, year_end: int, unit_type: str) -> str:
    if year_end is None:
        duration = 0
    else:
        duration = year_end - year_start

    # 타입 기반 기본값
    if unit_type in ('battle', 'treaty', 'coronation'):
        return 'evenementielle'
    if unit_type in ('era', 'age'):
        return 'longue_duree'

    # 기간 기반
    if duration <= 1:
        return 'evenementielle'
    elif duration <= 100:
        return 'conjuncture'
    else:
        return 'longue_duree'
```

---

## 예시 데이터

### 백년전쟁 계층

```
백년전쟁 (1337-1453)
├── unit_type: 'war'
├── scale: 'conjuncture' (116년)
├── scope_type: 'multi_region'
├── locations: [France, England, Flanders]
│
├── 에드워드 전쟁 (1337-1360)
│   ├── 크레시 전투 (1346) - battle, evenementielle
│   ├── 칼레 공성전 (1346-1347) - siege
│   └── 브레티니 조약 (1360) - treaty
│
├── 캐롤라인 전쟁 (1369-1389)
│   └── ...
│
└── 랭커스터 전쟁 (1415-1453)
    ├── 아쟁쿠르 전투 (1415) - battle
    ├── 잔 다르크 활동 (1429-1431)
    │   ├── 오를레앙 공성전 해제 (1429)
    │   └── 랭스 대관식 (1429)
    └── 카스티용 전투 (1453) - battle, 종전
```

### 르네상스 계층

```
르네상스 (1400-1600)
├── unit_type: 'movement'
├── scale: 'longue_duree'
├── scope_type: 'region'
├── locations: [Italy, Western Europe]
│
├── 이탈리아 르네상스 (1400-1527)
│   ├── 피렌체 전성기 (1434-1494)
│   │   └── 메디치 가문 집권 (1434)
│   └── 로마 르네상스 (1503-1527)
│
└── 북유럽 르네상스 (1500-1600)
    └── ...
```

---

## 마이그레이션 계획

### Phase 1: 새 테이블 생성

```sql
-- historical_units 테이블 생성 (기존 테이블 유지)
CREATE TABLE historical_units (...);
CREATE TABLE historical_unit_locations (...);
CREATE TABLE historical_unit_relations (...);
```

### Phase 2: 데이터 마이그레이션

```python
# events → historical_units
INSERT INTO historical_units (
    name, year_start, year_end, unit_type, scale, ...
)
SELECT
    name, year_start, year_end,
    CASE
        WHEN title LIKE '%Battle%' THEN 'battle'
        WHEN title LIKE '%War%' THEN 'war'
        WHEN title LIKE '%Treaty%' THEN 'treaty'
        ELSE 'event'
    END,
    CASE
        WHEN year_end - year_start <= 1 THEN 'evenementielle'
        WHEN year_end - year_start <= 100 THEN 'conjuncture'
        ELSE 'longue_duree'
    END,
    ...
FROM events;

# periods → historical_units
INSERT INTO historical_units (
    name, year_start, year_end, unit_type, scale, ...
)
SELECT
    name, year_start, year_end,
    'period',
    scale,  -- 기존 scale 그대로
    ...
FROM periods;
```

### Phase 3: API 전환

```python
# 기존 /events, /periods → /units 통합
@router.get("/units")
def get_units(
    unit_type: List[str] = Query(None),  # 필터
    scale: List[str] = Query(None),
    year_start: int = None,
    year_end: int = None,
):
    ...

# 하위 호환성 유지
@router.get("/events")  # deprecated, /units로 리다이렉트
@router.get("/periods")  # deprecated
```

### Phase 4: 기존 테이블 제거

```sql
-- 충분한 검증 후
DROP TABLE events;
DROP TABLE periods;
DROP TABLE event_locations;
DROP TABLE period_locations;
```

---

## Globe 시각화 연동

### 줌 레벨별 표시

```typescript
const getDisplayUnits = (units: HistoricalUnit[], altitude: number) => {
  return units.filter(unit => {
    // 줌 아웃 → longue_duree만
    if (altitude > 3.0) {
      return unit.scale === 'longue_duree'
    }
    // 중간 → conjuncture까지
    if (altitude > 1.5) {
      return ['longue_duree', 'conjuncture'].includes(unit.scale)
    }
    // 줌 인 → 전부
    return true
  })
}
```

### 계층 드릴다운

```
World View (altitude > 3)
  → "백년전쟁" 마커 1개

Region View (altitude 1.5-3)
  → "에드워드 전쟁", "캐롤라인 전쟁", "랭커스터 전쟁" 마커들

City View (altitude < 1.5)
  → 개별 전투들: 크레시, 아쟁쿠르, 카스티용...
```

---

## 유지할 별도 테이블

```
persons     ← 행위자 (사람)
locations   ← 공간 (장소)
polities    ← 행위자 (정치체/국가)
sources     ← 출처

historical_units ← 시간-공간 이벤트 (통합)
```

**관계:**
- Person ↔ HistoricalUnit (참여)
- Location ↔ HistoricalUnit (발생지)
- Polity ↔ HistoricalUnit (관련 국가)
- Source ↔ HistoricalUnit (출처)

---

## 예상 효과

| 항목 | Before | After |
|------|--------|-------|
| 테이블 수 | events + periods + 연결들 | historical_units + 2 |
| 중복 필드 | year_start 2개씩 | 통합 |
| 백년전쟁 표현 | 애매함 | war + 계층 |
| 줌 연동 | 별도 로직 | scale 기반 통합 |
| API 엔드포인트 | /events, /periods | /units |
