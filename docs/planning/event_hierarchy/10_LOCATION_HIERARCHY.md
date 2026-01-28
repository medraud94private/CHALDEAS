# 이벤트 계층화 - 장소 계층 구조

**작성일**: 2026-01-28
**출처**: `road_to_v3/HIERARCHICAL_LOCATION_SYSTEM.md` 통합
**목적**: Location도 Event처럼 계층 구조로 확장

---

## 1. 현재 문제점

1. **중복 좌표**: 같은 장소(로마)가 여러 이벤트에 각각 좌표로 저장됨
2. **일관성 없음**: 어떤 이벤트는 location_id, 어떤 건 직접 좌표
3. **다지역 불가**: "포에니 전쟁"처럼 여러 지역에 걸친 이벤트 표현 어려움
4. **계층 없음**: 로마 → 이탈리아 → 로마제국 관계 표현 불가

---

## 2. 스키마 확장

### 2.1 Alembic Migration

```python
def upgrade():
    # Location 계층화 컬럼 추가
    op.add_column('locations', sa.Column('location_type', sa.String(20)))
    # city, region, country, empire, cultural_sphere, sea, continent

    op.add_column('locations', sa.Column('parent_id', sa.Integer(),
                  sa.ForeignKey('locations.id')))

    op.add_column('locations', sa.Column('hierarchy_level', sa.Integer(), default=3))
    # 0: World, 1: Continent/Empire, 2: Region/Country, 3: City, 4: Site

    op.add_column('locations', sa.Column('display_zoom_min', sa.Float(), default=0))
    op.add_column('locations', sa.Column('display_zoom_max', sa.Float(), default=10))
```

### 2.2 Location Type

| Type | 설명 | Level | 예시 |
|------|------|-------|------|
| `cultural_sphere` | 문화권 | 1 | Mediterranean, Far East |
| `empire` | 제국/대국 | 1 | Roman Empire, Mongol Empire |
| `country` | 국가/왕국 | 2 | France, England |
| `region` | 지역/주 | 2 | Gaul, Italia, Hispania |
| `city` | 도시 | 3 | Rome, Athens, Paris |
| `site` | 특정 장소 | 4 | Colosseum, Acropolis |

---

## 3. 계층 예시

```
Mediterranean (cultural_sphere, Level 1)
├── Roman Empire (empire, Level 1)
│   ├── Italia (region, Level 2)
│   │   ├── Rome (city, Level 3)
│   │   │   └── Colosseum (site, Level 4)
│   │   ├── Pompeii (city, Level 3)
│   │   └── Naples (city, Level 3)
│   ├── Hispania (region, Level 2)
│   │   └── Carthago Nova (city, Level 3)
│   └── Aegyptus (region, Level 2)
│       └── Alexandria (city, Level 3)
├── Carthaginian Empire (empire, Level 1)
│   └── North Africa (region, Level 2)
│       └── Carthage (city, Level 3)
└── Hellenic World (cultural_sphere, Level 1)
    ├── Attica (region, Level 2)
    │   └── Athens (city, Level 3)
    └── Peloponnese (region, Level 2)
        └── Sparta (city, Level 3)
```

---

## 4. Event-Location 연결

### 4.1 기존 event_locations 테이블 확장

```sql
ALTER TABLE event_locations ADD COLUMN role VARCHAR(20) DEFAULT 'primary';
-- primary: 주요 발생지
-- secondary: 부차적 장소
-- origin: 출발지 (이동/원정)
-- destination: 도착지
-- affected: 영향받은 지역

ALTER TABLE event_locations ADD COLUMN sequence_order INTEGER DEFAULT 0;
-- 이동 이벤트의 경우 순서
```

### 4.2 다지역 이벤트 예시

**포에니 전쟁** (Aggregate Event):
```
event_id: 1001 (Punic Wars)
├── location_id: 100 (Rome) - role: origin
├── location_id: 101 (Carthage) - role: primary
├── location_id: 102 (Sicily) - role: affected
├── location_id: 103 (Hispania) - role: affected
└── location_id: 104 (North Africa) - role: destination
```

---

## 5. Globe 줌 레벨 연동

| 줌 레벨 | 표시되는 Location | 표시되는 Event |
|--------|------------------|----------------|
| 1-2 | cultural_sphere, empire | Era, Mega-Event |
| 3-4 | country, region | Aggregate |
| 5-6 | city | Major |
| 7+ | site | Minor |

---

## 6. API 확장

```
GET /api/v1/locations/hierarchy          # 계층적 장소 트리
GET /api/v1/locations/{id}/children      # 자식 장소들
GET /api/v1/locations/{id}/ancestors     # 상위 장소들
GET /api/v1/locations?level=2            # 레벨별 필터
GET /api/v1/locations?type=city          # 타입별 필터
```

---

## 7. 구현 체크리스트

### Phase 1: 스키마
- [ ] Alembic 마이그레이션 생성
- [ ] Location 모델 확장
- [ ] event_locations 테이블 확장

### Phase 2: 데이터
- [ ] 주요 Location에 hierarchy_level 설정
- [ ] parent_id 연결 (Rome → Italia → Roman Empire)
- [ ] location_type 분류

### Phase 3: API/Frontend
- [ ] 계층 API 추가
- [ ] Globe 줌 레벨 필터 연동

---

## 8. Event Hierarchy와의 통합

Event와 Location 모두 같은 계층 패턴:

| 컬럼 | events | locations |
|------|--------|-----------|
| 부모 참조 | parent_event_id | parent_id |
| 계층 레벨 | hierarchy_level | hierarchy_level |
| 타입 | aggregate_type | location_type |
| 줌 연동 | min_zoom_level | display_zoom_min/max |

→ **같은 마이그레이션에서 함께 처리 가능**
