# V3 System Gaps & Solutions

> **작성일**: 2026-01-16
> **상태**: 보완 계획
> **목적**: 기존 설계에서 누락된 시스템 요소 정리

---

## 누락 요소 분석

기존 V3 문서에서 다루지 않은 핵심 영역:

| 영역 | 현재 상태 | 영향도 |
|------|----------|--------|
| **검색/발견 시스템** | 단순 텍스트 검색만 | 높음 |
| **성능/캐싱** | 고려 없음 | 높음 |
| **하위 호환성** | 미정의 | 중간 |
| **테스트 전략** | 없음 | 중간 |
| **데이터 품질 관리** | 파편화 | 중간 |
| **관리자 대시보드** | 개념만 | 낮음 |
| **다국어 전략** | 필드만 정의 | 낮음 |

---

## 1. 검색 및 발견 시스템

### 현재 문제

```
현재: 단순 ILIKE 검색
SELECT * FROM events WHERE title ILIKE '%alexander%'

문제:
- Scale 무시 (도시 검색해도 전쟁 나옴)
- 유니버스 무시 (역사 검색해도 FGO 나옴)
- 계층 무시 (로마 검색해도 이탈리아 안 나옴)
- 관련성 순위 없음
```

### V3 검색 요구사항

```
┌─────────────────────────────────────────────────────────┐
│                   V3 Search System                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Query: "alexander the great"                           │
│                                                         │
│  Filters (자동):                                        │
│  ├── universe: historical (default)                    │
│  ├── scale: based on zoom level                        │
│  └── location: based on viewport                       │
│                                                         │
│  Results (ranked):                                      │
│  1. [Person] Alexander the Great (100% match)          │
│  2. [Unit] Battle of Gaugamela (related)               │
│  3. [Unit] Siege of Tyre (related)                     │
│  4. [Location] Alexandria (founded by)                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 검색 API 설계

```python
# GET /api/v3/search
@router.get("/search")
async def search_v3(
    q: str,                              # 검색어
    types: List[str] = ["all"],          # person/unit/location
    universe: str = "historical",        # historical/fgo/all
    scale: Optional[str] = None,         # evenementielle/conjuncture/longue_duree
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    location_id: Optional[int] = None,   # 해당 위치 내
    include_children: bool = True,       # 하위 계층 포함
    limit: int = 20,
    offset: int = 0
):
    """V3 통합 검색"""
    pass

# Response
{
  "query": "alexander",
  "filters": {"universe": "historical", "scale": null},
  "total": 127,
  "results": [
    {
      "type": "person",
      "id": 42,
      "name": "Alexander the Great",
      "score": 1.0,
      "snippet": "King of Macedon (356-323 BCE)...",
      "universe": "historical"
    },
    {
      "type": "unit",
      "id": 501,
      "name": "Battle of Gaugamela",
      "unit_type": "battle",
      "scale": "evenementielle",
      "score": 0.85,
      "relation": "participant"  # 왜 관련있는지
    }
  ]
}
```

### 검색 인덱싱 전략

```sql
-- Full-text search 인덱스
CREATE INDEX idx_units_fts ON historical_units
  USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));

CREATE INDEX idx_persons_fts ON persons
  USING gin(to_tsvector('english', name || ' ' || COALESCE(biography, '')));

-- 복합 필터링 인덱스
CREATE INDEX idx_units_search ON historical_units(universe_id, scale, unit_type);
CREATE INDEX idx_units_temporal ON historical_units(date_start, date_end);
```

### 관련성 순위 로직

```python
def calculate_relevance(entity, query, context):
    """검색 결과 관련성 점수"""
    score = 0.0

    # 1. 이름 매칭 (가장 중요)
    if query.lower() in entity.name.lower():
        score += 0.5
        if entity.name.lower().startswith(query.lower()):
            score += 0.3

    # 2. 관계 기반 (검색어와의 연결)
    if has_direct_relation(entity, query):
        score += 0.2

    # 3. 시대적 근접성 (현재 타임라인 기준)
    if context.get('current_year'):
        temporal_distance = abs(entity.year - context['current_year'])
        score += max(0, 0.1 - temporal_distance / 10000)

    # 4. 지역적 근접성 (현재 뷰포트 기준)
    if context.get('viewport'):
        if entity_in_viewport(entity, context['viewport']):
            score += 0.1

    return score
```

---

## 2. 성능 및 캐싱 전략

### 현재 문제

```
50,000+ HistoricalUnits
48,000+ Persons
15,000+ Locations

Globe에서 모든 마커 렌더링 시 성능 이슈 예상
```

### 성능 최적화 계층

```
┌─────────────────────────────────────────────────────────┐
│                 Performance Layers                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Layer 1: Database (Query Optimization)                 │
│  ├── 적절한 인덱스                                      │
│  ├── 파티셔닝 (년도별/유니버스별)                        │
│  └── Materialized view for aggregates                  │
│                                                         │
│  Layer 2: Application Cache (Redis/Memory)              │
│  ├── 자주 조회되는 엔티티 캐싱                          │
│  ├── 검색 결과 캐싱 (TTL: 5분)                         │
│  └── Timeline aggregate 캐싱                           │
│                                                         │
│  Layer 3: API Response (HTTP Caching)                   │
│  ├── ETag for conditional requests                     │
│  ├── Cache-Control headers                             │
│  └── CDN for static globe data                         │
│                                                         │
│  Layer 4: Frontend (Client-side)                        │
│  ├── React Query caching                               │
│  ├── Virtual scrolling for lists                       │
│  ├── Globe LOD (Level of Detail)                       │
│  └── Viewport culling (보이는 것만 렌더)                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Globe 성능 최적화

```typescript
// Globe 마커 최적화
interface GlobePerformanceConfig {
  // 줌 레벨별 최대 마커 수
  maxMarkersByZoom: {
    world: 500,      // altitude > 2.0
    continent: 1000, // altitude 1.0-2.0
    country: 2000,   // altitude 0.5-1.0
    region: 5000,    // altitude < 0.5
  },

  // LOD (Level of Detail)
  lodLevels: [
    { altitude: 2.0, clusterRadius: 600, showLabels: false },
    { altitude: 1.0, clusterRadius: 200, showLabels: false },
    { altitude: 0.5, clusterRadius: 50, showLabels: true },
    { altitude: 0.2, clusterRadius: 0, showLabels: true },
  ],

  // Viewport culling
  viewportPadding: 0.2,  // 뷰포트 외 20% 추가 로드
}

// 마커 데이터 페이징
async function loadMarkersForViewport(viewport, zoom, year) {
  const response = await fetch(`/api/v3/globe/markers`, {
    method: 'POST',
    body: JSON.stringify({
      bounds: viewport,
      altitude: zoom,
      year_range: [year - 50, year + 50],
      limit: getMaxMarkers(zoom),
      scale: getScaleForZoom(zoom),  // 줌에 맞는 스케일만
    })
  });
  return response.json();
}
```

### 캐싱 정책

```python
# Redis 캐싱 키 구조
CACHE_KEYS = {
    # 개별 엔티티 (5분)
    'unit:{id}': 300,
    'person:{id}': 300,
    'location:{id}': 300,

    # 검색 결과 (1분)
    'search:{hash}': 60,

    # 집계 (10분)
    'stats:units_by_scale': 600,
    'stats:timeline_density': 600,

    # Globe 데이터 (zoom별, 1분)
    'globe:markers:{viewport_hash}:{zoom}': 60,
}

class CacheService:
    async def get_unit(self, unit_id: int) -> Optional[dict]:
        key = f'unit:{unit_id}'
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)

        unit = await db.get_unit(unit_id)
        await redis.setex(key, 300, json.dumps(unit))
        return unit

    async def invalidate_unit(self, unit_id: int):
        """유닛 수정 시 캐시 무효화"""
        await redis.delete(f'unit:{unit_id}')
        # 관련 검색 캐시도 무효화
        await redis.delete_pattern('search:*')
```

---

## 3. 하위 호환성 전략

### API 버전 관리

```
/api/v1/events      → 유지 (deprecated, 1년)
/api/v1/periods     → 유지 (deprecated, 1년)
/api/v1/persons     → 유지

/api/v3/units       → 신규 (통합)
/api/v3/persons     → 업그레이드
/api/v3/locations   → 업그레이드
```

### V1 → V3 리다이렉트

```python
@router.get("/v1/events")
async def events_v1_compat(
    year: Optional[int] = None,
    limit: int = 100
):
    """V1 호환 - V3로 변환"""
    # V3 API 호출
    units = await units_service.list(
        unit_type=['battle', 'treaty', 'birth', 'death'],  # event 유형만
        scale='evenementielle',  # 단기 이벤트만
        year=year,
        limit=limit
    )

    # V1 응답 형식으로 변환
    return [unit_to_v1_event(u) for u in units]

def unit_to_v1_event(unit: HistoricalUnit) -> dict:
    """HistoricalUnit → V1 Event 변환"""
    return {
        'id': unit.id,
        'title': unit.name,
        'title_ko': unit.name_ko,
        'year': unit.date_start.year if unit.date_start else unit.year_start,
        'description': unit.description,
        'latitude': unit.locations[0].latitude if unit.locations else None,
        'longitude': unit.locations[0].longitude if unit.locations else None,
        # ... 기타 V1 필드
    }
```

### 클라이언트 마이그레이션 가이드

```markdown
## V1 → V3 마이그레이션

### Events → Units
- `/api/v1/events` → `/api/v3/units?type=battle,treaty,birth,death&scale=evenementielle`
- `event.year` → `unit.date_start` (DATE 타입)
- `event.latitude/longitude` → `unit.locations[0].latitude/longitude`

### Periods → Units
- `/api/v1/periods` → `/api/v3/units?type=period,era,movement&scale=conjuncture,longue_duree`
- 계층 관계는 `parent_id`로 표현

### 신규 기능
- `?universe=historical` 필터
- `?include_children=true` 계층 포함
- `unit.scale` 필드로 Braudel 시간 구분
```

---

## 4. 데이터 품질 관리 시스템

### 품질 점수 모델

```sql
CREATE TABLE entity_quality_scores (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,  -- 'unit', 'person', 'location'
    entity_id INTEGER NOT NULL,

    -- 개별 점수 (0-100)
    completeness_score INTEGER,   -- 필수 필드 채움률
    accuracy_score INTEGER,       -- Wikidata 일치율
    connectivity_score INTEGER,   -- 관계 연결 수
    source_score INTEGER,         -- 출처 품질

    -- 종합 점수
    total_score INTEGER GENERATED ALWAYS AS (
        (completeness_score + accuracy_score + connectivity_score + source_score) / 4
    ) STORED,

    -- 이슈 목록
    issues JSONB,  -- [{type: 'missing_date', severity: 'high'}, ...]

    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(entity_type, entity_id)
);
```

### 품질 검사 로직

```python
class DataQualityChecker:
    """데이터 품질 자동 검사"""

    RULES = {
        'unit': [
            ('missing_date', lambda u: u.date_start is None, 'high'),
            ('missing_location', lambda u: not u.locations and u.scope_type == 'point', 'medium'),
            ('orphan_unit', lambda u: not u.period_relations, 'low'),
            ('date_order', lambda u: u.date_end and u.date_start > u.date_end, 'high'),
            ('no_wikidata', lambda u: not u.wikidata_id, 'low'),
        ],
        'person': [
            ('missing_dates', lambda p: not p.birth_year and not p.death_year, 'medium'),
            ('no_events', lambda p: not p.events, 'low'),
            ('no_wikidata', lambda p: not p.wikidata_id, 'low'),
        ],
        'location': [
            ('no_coordinates', lambda l: not l.latitude, 'high'),
            ('no_parent', lambda l: not l.parent_id and l.location_type != 'continent', 'medium'),
        ]
    }

    def check_entity(self, entity_type: str, entity) -> QualityScore:
        issues = []
        for rule_name, check_fn, severity in self.RULES[entity_type]:
            if check_fn(entity):
                issues.append({'type': rule_name, 'severity': severity})

        return QualityScore(
            completeness=self._calc_completeness(entity, entity_type),
            accuracy=self._calc_accuracy(entity),
            connectivity=self._calc_connectivity(entity),
            source=self._calc_source_quality(entity),
            issues=issues
        )

    def _calc_completeness(self, entity, entity_type) -> int:
        """필수 필드 채움률"""
        required = {
            'unit': ['name', 'date_start', 'unit_type', 'scale'],
            'person': ['name', 'birth_year'],
            'location': ['name', 'latitude', 'longitude'],
        }
        filled = sum(1 for f in required[entity_type] if getattr(entity, f, None))
        return int(filled / len(required[entity_type]) * 100)
```

### 품질 대시보드 API

```python
@router.get("/admin/quality/summary")
async def quality_summary():
    """전체 품질 요약"""
    return {
        'units': {
            'total': 50000,
            'high_quality': 35000,  # score >= 80
            'medium_quality': 10000,  # score 50-79
            'low_quality': 5000,  # score < 50
            'top_issues': [
                {'type': 'missing_date', 'count': 8000},
                {'type': 'orphan_unit', 'count': 5000},
                {'type': 'no_wikidata', 'count': 15000},
            ]
        },
        'persons': { ... },
        'locations': { ... }
    }

@router.get("/admin/quality/issues/{issue_type}")
async def get_entities_with_issue(issue_type: str, limit: int = 100):
    """특정 이슈를 가진 엔티티 목록"""
    return db.query(EntityQualityScore).filter(
        EntityQualityScore.issues.contains([{'type': issue_type}])
    ).limit(limit).all()
```

---

## 5. 테스트 전략

### 테스트 피라미드

```
          ╱╲
         ╱  ╲  E2E (5%)
        ╱────╲  - Full flow tests
       ╱      ╲  - Critical paths only
      ╱────────╲
     ╱          ╲  Integration (25%)
    ╱────────────╲  - API endpoints
   ╱              ╲  - DB operations
  ╱────────────────╲  - Wikidata integration
 ╱                  ╲
╱────────────────────╲  Unit (70%)
  - Models validation
  - Service logic
  - Utility functions
```

### 핵심 테스트 케이스

```python
# tests/test_historical_unit.py

class TestHistoricalUnit:
    """HistoricalUnit 모델 테스트"""

    def test_unit_type_classification(self):
        """unit_type 분류 검증"""
        battle = HistoricalUnit(unit_type='battle', scale='evenementielle')
        war = HistoricalUnit(unit_type='war', scale='conjuncture')
        era = HistoricalUnit(unit_type='era', scale='longue_duree')

        assert battle.is_event()
        assert war.is_period()
        assert era.is_period()

    def test_hierarchy_traversal(self):
        """계층 구조 탐색"""
        # 백년전쟁 → 크레시 전투 → 에드워드 3세 참전
        hundred_years = create_unit(name="Hundred Years' War", scale='conjuncture')
        crecy = create_unit(name="Battle of Crécy", parent=hundred_years)

        assert crecy.parent_id == hundred_years.id
        assert hundred_years in crecy.get_ancestors()

    def test_date_precision(self):
        """날짜 정밀도 처리"""
        unit = HistoricalUnit(
            date_start=date(1429, 5, 8),
            date_start_precision='day'
        )
        assert unit.format_date_start() == "May 8, 1429"

        unit.date_start_precision = 'month'
        assert unit.format_date_start() == "May 1429"

        unit.date_start_precision = 'year'
        assert unit.format_date_start() == "1429"

# tests/test_search_api.py

class TestSearchAPI:
    """검색 API 테스트"""

    async def test_search_with_universe_filter(self, client):
        """유니버스 필터 테스트"""
        # 역사적 잔느만 검색
        resp = await client.get('/api/v3/search?q=jeanne&universe=historical')
        assert all(r['universe'] == 'historical' for r in resp.json()['results'])

        # FGO 포함 검색
        resp = await client.get('/api/v3/search?q=jeanne&universe=all')
        universes = {r['universe'] for r in resp.json()['results']}
        assert 'fgo' in universes or len(universes) >= 1

# tests/integration/test_wikidata_enrichment.py

class TestWikidataEnrichment:
    """Wikidata 보강 통합 테스트"""

    async def test_enrich_dates(self):
        """날짜 보강 테스트"""
        unit = create_unit(wikidata_id='Q12345', date_start=None)

        await wikidata_enricher.enrich_dates(unit)

        assert unit.date_start is not None
        assert unit.date_start_precision in ['day', 'month', 'year']
```

---

## 6. 관리자 대시보드

### 대시보드 기능

```
┌─────────────────────────────────────────────────────────────┐
│  CHALDEAS Admin Dashboard                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Overview ───────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  Units: 52,341    Persons: 48,373    Locations: 15,234│  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │  │
│  │  Today: +127      Today: +15         Today: +8       │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Pending Approvals (12) ─────────────────────────────┐  │
│  │  ☐ New unit: "Battle of Hastings" (user: john)       │  │
│  │  ☐ Edit: "Alexander the Great" - birth date fix      │  │
│  │  ☐ New person: "Cleopatra VII" (user: maria)         │  │
│  │  [View All →]                                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Quality Issues ─────────────────────────────────────┐  │
│  │  ⚠ Missing dates: 8,234 units                        │  │
│  │  ⚠ Orphan units: 5,123 (no period link)              │  │
│  │  ⚠ No Wikidata: 15,234 entities                      │  │
│  │  [Fix Wizard →]                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Ingestion Status ───────────────────────────────────┐  │
│  │  Wikipedia sync: 3 days ago (next: tomorrow)         │  │
│  │  Wikidata enrichment: Running (45%)                  │  │
│  │  Story generation: Idle                               │  │
│  │  [Trigger Sync →]                                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Admin API 엔드포인트

```python
# backend/app/api/v3/admin.py

@router.get("/admin/dashboard")
async def admin_dashboard():
    """관리자 대시보드 데이터"""
    return {
        'stats': {
            'units': await count_units(),
            'persons': await count_persons(),
            'locations': await count_locations(),
            'today': await get_today_additions(),
        },
        'pending': await get_pending_submissions(limit=5),
        'quality': await get_quality_summary(),
        'jobs': await get_job_status(),
    }

@router.get("/admin/pending")
async def list_pending(status: str = 'pending', limit: int = 50):
    """승인 대기 목록"""
    pass

@router.post("/admin/approve/{submission_id}")
async def approve_submission(submission_id: int, admin: Admin = Depends()):
    """제출 승인"""
    pass

@router.post("/admin/reject/{submission_id}")
async def reject_submission(submission_id: int, reason: str, admin: Admin = Depends()):
    """제출 거부"""
    pass

@router.post("/admin/bulk-fix")
async def bulk_fix_issues(issue_type: str, fix_method: str, admin: Admin = Depends()):
    """일괄 이슈 수정 (예: Wikidata로 날짜 채우기)"""
    pass
```

---

## 7. 다국어 전략

### 현재 상태

```python
# 현재: 필드별 번역
class Event:
    title: str          # 영어
    title_ko: str       # 한국어
    description: str    # 영어
    description_ko: str # 한국어
```

### V3 다국어 전략

```python
# 옵션 1: 필드 확장 (간단)
class HistoricalUnit:
    name: str           # 영어 (기본)
    name_ko: str        # 한국어
    name_ja: str        # 일본어

# 옵션 2: 별도 번역 테이블 (확장성)
class UnitTranslation:
    unit_id: int
    language: str       # 'en', 'ko', 'ja', 'zh', ...
    name: str
    description: str

# 권장: 옵션 1 (핵심 언어) + 옵션 2 (추가 언어)
```

### 다국어 API

```python
@router.get("/units/{id}")
async def get_unit(id: int, lang: str = 'en'):
    """언어별 유닛 조회"""
    unit = await db.get_unit(id)

    # 언어 우선순위: 요청 언어 → 영어 → 있는 것
    return {
        'id': unit.id,
        'name': get_localized(unit, 'name', lang),
        'description': get_localized(unit, 'description', lang),
        'available_languages': ['en', 'ko', 'ja'],
    }

def get_localized(entity, field: str, lang: str) -> str:
    """지역화된 필드 값 반환"""
    localized_field = f'{field}_{lang}' if lang != 'en' else field
    value = getattr(entity, localized_field, None)
    if value:
        return value
    return getattr(entity, field, '')  # fallback to English
```

---

## 구현 우선순위

### Phase 1: 핵심 (V3 필수)

1. **검색 시스템 V3** - scale/universe 필터링
2. **성능 기본** - 인덱스, 쿼리 최적화
3. **품질 점수** - 기본 completeness 체크

### Phase 2: 확장 (V3 완성 후)

4. **캐싱 레이어** - Redis 도입
5. **관리자 대시보드** - 기본 UI
6. **테스트 커버리지** - 핵심 로직 70%

### Phase 3: 고도화

7. **하위 호환성** - V1 deprecation 시작
8. **다국어 확장** - 일본어, 중국어
9. **고급 검색** - 시맨틱 검색, 추천

---

## POST_EXTRACTION_TASKS.md 업데이트 필요

```
기존 Phase에 추가:

Phase B-4: 검색 인덱스 생성
    ├── FTS 인덱스
    └── 복합 필터 인덱스

Phase E-2: 성능 최적화
    ├── 쿼리 최적화
    ├── Globe LOD 구현
    └── 캐싱 레이어

Phase H: 운영 도구 (신규)
    ├── 관리자 대시보드
    ├── 품질 모니터링
    └── 하위 호환 API
```
