# 데이터 소스 및 수집 파이프라인

## 상태: 구현 완료 (Phase 2)

## 1. 데이터 소스 개요

CHALDEAS는 다음 오픈소스 디지털 아카이브들에서 데이터를 수집합니다:

| 아카이브 | 분야 | 데이터 종류 | 라이선스 | 상태 |
|----------|------|-------------|----------|------|
| **Pleiades Gazetteer** | 고대 지리 | 34,000+ 장소/좌표 | CC BY 3.0 | ✅ 구현됨 |
| **Wikidata** | 종합 | 이벤트/인물/도시 | CC0 | ✅ 구현됨 |
| **Perseus Digital Library** | 그리스/로마 | 고전 텍스트 | CC BY-SA | ✅ 구현됨 |
| **Chinese Text Project** | 중국 고전 | 한문 텍스트 | 비상업적 | ✅ 구현됨 |
| **Project Gutenberg** | 일반 문학 | 6만+ 전자책 | Public Domain | ✅ 구현됨 |
| **The Latin Library** | 라틴어 | 라틴 텍스트 | Educational | ✅ 구현됨 |
| **BIBLIOTHECA AUGUSTANA** | 그리스/라틴 | 고전 텍스트 | Academic | ✅ 구현됨 |

---

## 2. 데이터 파이프라인

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CHALDEAS Data Pipeline                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  STEP 1: COLLECT                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  python data/scripts/collect_all.py --source all            │    │
│  │                                                             │    │
│  │  ├── Pleiades   → data/raw/pleiades/                       │    │
│  │  ├── Wikidata   → data/raw/wikidata/                       │    │
│  │  ├── Perseus    → data/raw/perseus/                        │    │
│  │  ├── CText      → data/raw/ctext/                          │    │
│  │  ├── Gutenberg  → data/raw/gutenberg/                      │    │
│  │  ├── Latin Lib  → data/raw/latin_library/                  │    │
│  │  └── Augustana  → data/raw/augustana/                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  STEP 2: TRANSFORM & ENRICH                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  python data/scripts/transform_data.py                      │    │
│  │                                                             │    │
│  │  • Parse raw data into unified format                       │    │
│  │  • Resolve missing coordinates via GeoResolver             │    │
│  │  • Categorize events                                        │    │
│  │  • Estimate importance                                      │    │
│  │                                                             │    │
│  │  Output: data/processed/                                   │    │
│  │    ├── events_wikidata.json                                │    │
│  │    ├── persons_wikidata.json                               │    │
│  │    ├── locations_pleiades.json                             │    │
│  │    └── transform_stats.json                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  STEP 3: IMPORT TO DATABASE                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  python data/scripts/import_to_db.py                        │    │
│  │                                                             │    │
│  │  • Create/update PostgreSQL tables                          │    │
│  │  • Import events, persons, locations                        │    │
│  │  • Create relationships                                     │    │
│  │  • Generate indexes                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 수집기 상세

### 3.1 Pleiades Collector
**경로**: `data/scripts/collectors/pleiades.py`

고대 세계의 지명과 좌표를 수집합니다.

```bash
python collect_all.py --source pleiades
```

- **데이터**: JSON 덤프 (~50MB gzip)
- **내용**: 34,000+ 고대 장소
- **출력**:
  - `pleiades_raw.json` - 원본 데이터
  - `pleiades_locations.json` - 정제된 위치 데이터

### 3.2 Wikidata Collector
**경로**: `data/scripts/collectors/wikidata.py`

SPARQL 쿼리로 역사적 데이터를 수집합니다.

```bash
python collect_all.py --source wikidata
```

- **쿼리 대상**:
  - 역사적 이벤트 (전투, 전쟁, 조약 등)
  - 역사적 인물 (1800년 이전 출생)
  - 고대 도시 및 유적지
- **출력**:
  - `wikidata_events.json` - 10,000개 이벤트
  - `wikidata_persons.json` - 10,000명 인물
  - `wikidata_cities.json` - 5,000개 도시

### 3.3 Perseus Collector
**경로**: `data/scripts/collectors/perseus.py`

CTS API를 통해 그리스/로마 고전 텍스트 메타데이터를 수집합니다.

```bash
python collect_all.py --source perseus
```

- **API**: CTS (Canonical Text Services)
- **데이터**: 그리스/라틴 고전 목록
- **출력**:
  - `perseus_catalog.json` - 전체 카탈로그
  - `perseus_works.json` - 작품 메타데이터

### 3.4 Other Collectors

| 수집기 | 설명 |
|--------|------|
| `ctext.py` | 중국 고전 텍스트 (API 키 필요) |
| `gutenberg.py` | Project Gutenberg 카탈로그 및 텍스트 |
| `latin_library.py` | 라틴어 텍스트 메타데이터 |
| `bibliotheca_augustana.py` | 그리스/라틴 고전 메타데이터 |

---

## 4. 위치 해석 (GeoResolver)

**경로**: `data/scripts/geo_resolver.py`

좌표가 없는 위치를 해석합니다.

```python
resolver = GeoResolver(pleiades_path="data/raw/pleiades/pleiades_locations.json")

result = await resolver.resolve("Marathon")
# ResolvedLocation(
#   name="Marathon",
#   latitude=38.1536,
#   longitude=23.9633,
#   source="pleiades",
#   confidence=0.95
# )
```

### 해석 우선순위

1. **Pleiades** (신뢰도 95%) - 고대 장소
2. **Wikidata SPARQL** (신뢰도 90%) - 일반 위치
3. **World Historical Gazetteer** (신뢰도 85%) - 역사적 지명
4. **고대 지역 매핑** (신뢰도 60%) - 지역 중심
5. **국가 중심점** (신뢰도 30%) - 최후 수단

---

## 5. 데이터 변환

**경로**: `data/scripts/transform_data.py`

원시 데이터를 통합 형식으로 변환합니다.

### 통합 이벤트 형식

```json
{
  "id": "wd_Q190834",
  "title": "Battle of Marathon",
  "title_ko": null,
  "description": "Battle between Athens and Persia",
  "date_start": -490,
  "date_end": null,
  "date_precision": "year",
  "location_name": "Marathon",
  "latitude": 38.1536,
  "longitude": 23.9633,
  "location_source": "pleiades",
  "location_confidence": 0.95,
  "category": "battle",
  "importance": 5,
  "source_type": "wikidata",
  "source_id": "Q190834",
  "source_url": "https://www.wikidata.org/wiki/Q190834",
  "related_persons": [],
  "related_events": [],
  "tags": ["Greece"]
}
```

### 통합 인물 형식

```json
{
  "id": "wd_Q859",
  "name": "Plato",
  "name_ko": null,
  "description": "Classical Greek philosopher",
  "birth_year": -428,
  "death_year": -348,
  "birth_place": "Athens",
  "birth_latitude": 37.9838,
  "birth_longitude": 23.7275,
  "death_place": "Athens",
  "death_latitude": 37.9838,
  "death_longitude": 23.7275,
  "occupation": "philosopher",
  "source_type": "wikidata",
  "source_id": "Q859",
  "related_events": [],
  "tags": []
}
```

---

## 6. 데이터베이스 임포트

**경로**: `data/scripts/import_to_db.py`

변환된 데이터를 PostgreSQL에 임포트합니다.

```bash
# 전체 임포트
python import_to_db.py --input data/processed

# 기존 데이터 삭제 후 임포트
python import_to_db.py --input data/processed --clear
```

### 생성되는 테이블

- `categories` - 이벤트 카테고리
- `locations` - 장소 (좌표 포함)
- `events` - 역사적 이벤트
- `persons` - 역사적 인물
- `sources` - 출처 정보
- `event_relationships` - 이벤트 간 관계
- `event_persons` - 이벤트-인물 관계

---

## 7. 실행 방법

### 전체 파이프라인 실행

```bash
# 1. 데이터 수집 (수 시간 소요)
cd C:\Projects\Chaldeas
python data/scripts/collect_all.py --source all

# 2. 데이터 변환
python data/scripts/transform_data.py

# 3. 데이터베이스 임포트
python data/scripts/import_to_db.py
```

### 개별 소스 수집

```bash
# Wikidata만 수집
python data/scripts/collect_all.py --source wikidata

# Pleiades만 수집
python data/scripts/collect_all.py --source pleiades
```

---

## 8. 예상 데이터 규모

| 소스 | 항목 수 | 용량 |
|------|---------|------|
| Pleiades 장소 | ~34,000 | ~100MB |
| Wikidata 이벤트 | ~10,000 | ~20MB |
| Wikidata 인물 | ~10,000 | ~25MB |
| Wikidata 도시 | ~5,000 | ~10MB |
| Perseus 작품 | ~500+ | ~5MB |
| Gutenberg 카탈로그 | ~60,000 | ~50MB |
| Latin Library 메타 | ~1,000 | ~2MB |
| Augustana 메타 | ~500 | ~1MB |

**총 예상**: ~200MB+ (텍스트 미포함)

---

## 9. 라이선스 정보

| 소스 | 라이선스 | 상업적 사용 |
|------|----------|-------------|
| Pleiades | CC BY 3.0 | ✅ 가능 (출처 표기) |
| Wikidata | CC0 | ✅ 가능 |
| Perseus | CC BY-SA | ✅ 가능 (동일 조건) |
| CText | 비상업적 | ❌ 비상업만 |
| Gutenberg | Public Domain | ✅ 가능 |
| Latin Library | Educational | ⚠️ 교육용 |
| Augustana | Academic | ⚠️ 학술용 |

---

## 10. 향후 계획

### Phase 3: 텍스트 인덱싱
- 전체 텍스트 다운로드
- 벡터 임베딩 생성
- 시맨틱 검색 구현

### Phase 4: 자동 관계 추출
- NLP로 인물-이벤트 관계 추출
- 인과관계 자동 생성
- 시간순 연결

### Phase 5: 다국어 지원
- 한국어 번역 자동화
- 다국어 검색 지원
