# Multiverse 데이터 모델 - 역사 + 창작물 통합 관리

## 개요

역사적 데이터와 창작물(FGO 등) 데이터를 **연결하되 격리**하는 구조.

```
역사적 잔느 다르크 ◄────링크────► FGO 잔느 (Ruler)
        │                              │
        │                              ├── FGO 잔느 얼터
        │                              └── FGO 잔느 산타 릴리
        │
        └── 동일인물 아님, 하지만 "기반"
```

---

## 핵심 개념: Universe (세계관)

### Universe 정의

```sql
CREATE TABLE universes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,  -- 'historical', 'fgo', 'tsukihime', etc.
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100),
    description TEXT,

    -- 메타데이터
    is_canonical BOOLEAN DEFAULT FALSE,  -- TRUE = 역사 (기준 세계)
    parent_universe_id INTEGER REFERENCES universes(id),  -- 파생 관계

    -- 표시 설정
    color VARCHAR(7),  -- UI 색상 (#FF6B6B)
    icon VARCHAR(50),  -- 아이콘

    created_at TIMESTAMP DEFAULT NOW()
);

-- 기본 Universe
INSERT INTO universes (code, name, is_canonical) VALUES
    ('historical', 'Historical Reality', TRUE),
    ('fgo', 'Fate/Grand Order', FALSE),
    ('fgo-arcade', 'FGO Arcade', FALSE),
    ('strange-fake', 'Fate/strange Fake', FALSE),
    ('tsukihime', 'Tsukihime', FALSE);
```

### 엔티티에 Universe 추가

```sql
-- persons 테이블 확장
ALTER TABLE persons ADD COLUMN universe_id INTEGER REFERENCES universes(id);
ALTER TABLE persons ADD COLUMN canonical_id INTEGER REFERENCES persons(id);

-- historical_units 테이블 확장
ALTER TABLE historical_units ADD COLUMN universe_id INTEGER REFERENCES universes(id);
ALTER TABLE historical_units ADD COLUMN canonical_id INTEGER REFERENCES historical_units(id);

-- locations 테이블 확장
ALTER TABLE locations ADD COLUMN universe_id INTEGER REFERENCES universes(id);
ALTER TABLE locations ADD COLUMN canonical_id INTEGER REFERENCES locations(id);

-- 기본값: historical
ALTER TABLE persons ALTER COLUMN universe_id SET DEFAULT 1;
ALTER TABLE historical_units ALTER COLUMN universe_id SET DEFAULT 1;
ALTER TABLE locations ALTER COLUMN universe_id SET DEFAULT 1;
```

---

## 데이터 구조 예시

### 잔느 다르크 (Person)

```
┌─────────────────────────────────────────────────────────────────┐
│ Historical Universe (canonical)                                  │
├─────────────────────────────────────────────────────────────────┤
│ Person #1                                                       │
│ ├── name: "Jeanne d'Arc"                                        │
│ ├── universe_id: 1 (historical)                                 │
│ ├── canonical_id: NULL (이게 원본)                               │
│ ├── birth_year: 1412                                            │
│ ├── death_year: 1431                                            │
│ └── wikidata_id: Q7226                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ canonical_id = 1
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FGO Universe                                                     │
├─────────────────────────────────────────────────────────────────┤
│ Person #1001                                                    │
│ ├── name: "Jeanne d'Arc"                                        │
│ ├── name_variant: "Ruler"                                       │
│ ├── universe_id: 2 (fgo)                                        │
│ ├── canonical_id: 1 (역사적 잔느 참조)                           │
│ ├── servant_class: "Ruler"                                      │
│ └── fgo_id: 59                                                  │
│                                                                 │
│ Person #1002                                                    │
│ ├── name: "Jeanne d'Arc (Alter)"                                │
│ ├── universe_id: 2 (fgo)                                        │
│ ├── canonical_id: 1 (역사적 잔느 참조)                           │
│ ├── servant_class: "Avenger"                                    │
│ └── fgo_id: 106                                                 │
│                                                                 │
│ Person #1003                                                    │
│ ├── name: "Jeanne d'Arc (Alter Santa Lily)"                     │
│ ├── universe_id: 2 (fgo)                                        │
│ ├── canonical_id: 1 (역사적 잔느 참조)                           │
│ ├── servant_class: "Lancer"                                     │
│ └── fgo_id: 141                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 특이점 (Historical Unit)

```
┌─────────────────────────────────────────────────────────────────┐
│ Historical Universe                                              │
├─────────────────────────────────────────────────────────────────┤
│ HistoricalUnit #501                                             │
│ ├── name: "Siege of Orléans"                                    │
│ ├── unit_type: "siege"                                          │
│ ├── year_start: 1428                                            │
│ ├── year_end: 1429                                              │
│ ├── universe_id: 1 (historical)                                 │
│ └── canonical_id: NULL                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FGO Universe                                                     │
├─────────────────────────────────────────────────────────────────┤
│ HistoricalUnit #5001                                            │
│ ├── name: "Orleans Singularity"                                 │
│ ├── unit_type: "singularity"                                    │
│ ├── universe_id: 2 (fgo)                                        │
│ ├── canonical_id: 501 (역사적 오를레앙 공성전 참조)              │
│ ├── chapter_number: 1                                           │
│ └── subtitle: "Hundred Years' War of the Evil Dragons"          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 쿼리 패턴

### 1. 역사 데이터만 조회 (기본)

```sql
-- 역사적 인물만
SELECT * FROM persons WHERE universe_id = 1;

-- 또는 is_canonical 활용
SELECT p.* FROM persons p
JOIN universes u ON p.universe_id = u.id
WHERE u.is_canonical = TRUE;
```

### 2. 특정 세계관 데이터 조회

```sql
-- FGO 서번트만
SELECT * FROM persons WHERE universe_id = 2;

-- FGO 특이점만
SELECT * FROM historical_units WHERE universe_id = 2;
```

### 3. 모든 버전 조회 (크로스 유니버스)

```sql
-- 잔느 다르크의 모든 버전
SELECT p.*, u.name as universe_name
FROM persons p
JOIN universes u ON p.universe_id = u.id
WHERE p.id = 1 OR p.canonical_id = 1;
```

### 4. 역사 인물 + 파생 캐릭터 수

```sql
-- 각 역사 인물별 창작물 등장 횟수
SELECT
    h.id,
    h.name,
    COUNT(f.id) as fictional_versions
FROM persons h
LEFT JOIN persons f ON f.canonical_id = h.id
WHERE h.universe_id = 1  -- 역사적 인물만
GROUP BY h.id, h.name
ORDER BY fictional_versions DESC;
```

---

## API 설계

### 기본: Universe 필터링

```
# 역사 데이터만 (기본값)
GET /api/v3/persons?universe=historical
GET /api/v3/units?universe=historical

# FGO 데이터만
GET /api/v3/persons?universe=fgo
GET /api/v3/units?universe=fgo

# 모든 세계관
GET /api/v3/persons?universe=all

# 여러 세계관
GET /api/v3/persons?universe=historical,fgo
```

### 크로스 레퍼런스

```
# 역사적 잔느의 모든 파생 버전
GET /api/v3/persons/1/variants

Response:
{
  "canonical": {
    "id": 1,
    "name": "Jeanne d'Arc",
    "universe": "historical"
  },
  "variants": [
    {"id": 1001, "name": "Jeanne d'Arc (Ruler)", "universe": "fgo"},
    {"id": 1002, "name": "Jeanne d'Arc (Alter)", "universe": "fgo"},
    {"id": 1003, "name": "Jeanne d'Arc (Alter Santa Lily)", "universe": "fgo"}
  ]
}
```

### FGO 전용 필드

```
# FGO 서번트 상세
GET /api/v3/fgo/servants/59

Response:
{
  "id": 1001,
  "name": "Jeanne d'Arc",
  "class": "Ruler",
  "rarity": 5,
  "canonical_person": {
    "id": 1,
    "name": "Jeanne d'Arc",
    "birth_year": 1412,
    "death_year": 1431
  },
  "noble_phantasm": "Luminosité Eternelle",
  ...
}
```

---

## Frontend 처리

### Universe Selector

```typescript
// 세계관 선택 컴포넌트
interface UniverseSelector {
  selected: 'historical' | 'fgo' | 'all';
  onChange: (universe: string) => void;
}

// Globe Store 확장
interface GlobeState {
  // ... 기존
  activeUniverse: string;  // 'historical' | 'fgo' | 'all'
  setActiveUniverse: (universe: string) => void;
}
```

### 시각적 구분

```typescript
// Universe별 색상/스타일
const UNIVERSE_STYLES = {
  historical: {
    markerColor: '#00d4ff',  // Cyan
    labelPrefix: '',
  },
  fgo: {
    markerColor: '#ff6b6b',  // Red
    labelPrefix: '⚔️ ',
    glowEffect: true,
  },
};
```

### 연결 표시

```typescript
// 역사 인물 상세에서 FGO 버전 표시
const PersonDetail = ({ person }) => {
  const { variants } = useVariants(person.id);

  return (
    <div>
      <h1>{person.name}</h1>
      {/* 역사 정보 */}

      {variants.length > 0 && (
        <div className="variants-section">
          <h3>창작물 등장</h3>
          {variants.map(v => (
            <VariantCard
              key={v.id}
              variant={v}
              universe={v.universe}
            />
          ))}
        </div>
      )}
    </div>
  );
};
```

---

## 데이터 진입 경로 확장

### FGO 데이터 임포트

```python
class FGODataImporter:
    """FGO 게임 데이터 임포트"""

    UNIVERSE_ID = 2  # fgo

    def import_servant(self, servant_data: dict):
        # 1. 역사적 인물 매칭
        canonical = self.find_canonical_person(servant_data['name'])

        # 2. FGO Person 생성
        person = Person(
            name=servant_data['name'],
            universe_id=self.UNIVERSE_ID,
            canonical_id=canonical.id if canonical else None,
            # FGO 전용 필드
            extra_data={
                'servant_class': servant_data['class'],
                'rarity': servant_data['rarity'],
                'fgo_id': servant_data['id'],
                'noble_phantasm': servant_data['np'],
            }
        )
        db.add(person)

    def find_canonical_person(self, name: str) -> Optional[Person]:
        """FGO 캐릭터명으로 역사적 인물 찾기"""
        # "Jeanne d'Arc (Alter)" → "Jeanne d'Arc"
        base_name = re.sub(r'\s*\([^)]+\)\s*', '', name).strip()

        return db.query(Person).filter(
            Person.universe_id == 1,  # historical
            Person.name.ilike(f'%{base_name}%')
        ).first()
```

### 사용자 연결 제안

```python
# 사용자가 연결 제안
POST /api/v3/suggest-link
{
  "source_id": 1001,           # FGO 잔느
  "source_universe": "fgo",
  "target_id": 1,              # 역사적 잔느
  "target_universe": "historical",
  "relation": "based_on"
}
```

---

## 확장 가능성

### 다른 창작물 추가

```sql
INSERT INTO universes (code, name, parent_universe_id) VALUES
    ('fgo-arcade', 'FGO Arcade', 2),        -- FGO의 파생
    ('fate-zero', 'Fate/Zero', NULL),
    ('fate-sn', 'Fate/stay night', NULL),
    ('apocrypha', 'Fate/Apocrypha', NULL),
    ('extella', 'Fate/EXTELLA', NULL);
```

### Universe 간 관계

```sql
-- Universe 관계 테이블 (선택적)
CREATE TABLE universe_relations (
    id SERIAL PRIMARY KEY,
    source_universe_id INTEGER REFERENCES universes(id),
    target_universe_id INTEGER REFERENCES universes(id),
    relation_type VARCHAR(30),  -- 'spinoff', 'parallel', 'sequel'
    UNIQUE(source_universe_id, target_universe_id)
);
```

---

## 데이터 격리 보장

### 1. 기본 쿼리 필터

```python
# 모든 API에 universe 필터 기본 적용
class BaseRepository:
    def get_all(self, universe: str = 'historical'):
        query = self.session.query(self.model)
        if universe != 'all':
            query = query.filter(self.model.universe_id == get_universe_id(universe))
        return query.all()
```

### 2. 데이터 무결성

```sql
-- canonical_id는 반드시 is_canonical=TRUE인 universe의 엔티티만 참조
ALTER TABLE persons ADD CONSTRAINT fk_canonical_historical
    CHECK (canonical_id IS NULL OR EXISTS (
        SELECT 1 FROM persons p
        JOIN universes u ON p.universe_id = u.id
        WHERE p.id = canonical_id AND u.is_canonical = TRUE
    ));
```

### 3. 권한 분리 (선택적)

```python
# 역사 데이터 수정: 관리자만
# 창작물 데이터 수정: 해당 분야 큐레이터
class PermissionChecker:
    def can_edit(self, user, entity):
        if entity.universe.is_canonical:
            return user.is_admin
        return user.has_permission(f'edit_{entity.universe.code}')
```

---

## 요약

| 구분 | 역사 데이터 | 창작물 데이터 |
|------|------------|--------------|
| universe_id | 1 (historical) | 2+ (fgo, etc.) |
| canonical_id | NULL | 역사 인물 ID |
| 기본 표시 | O | X (명시적 선택) |
| 수정 권한 | 관리자 | 해당 큐레이터 |
| Wikidata 연동 | O | X |
| 검색 기본 | 포함 | 제외 |
