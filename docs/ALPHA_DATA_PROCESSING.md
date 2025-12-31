# CHALDEAS Alpha 데이터 처리 계획

> Last Updated: 2025-12-31
> 목표: Raw 데이터 → 지구본/타임라인/검색용 구조화 데이터로 변환

---

## 현재 문제점

| 문제 | 설명 |
|------|------|
| **비구조화** | Raw JSON/텍스트만 있음, 정규화 안 됨 |
| **좌표 없음** | 대부분 위치 데이터에 lat/lng 없음 |
| **날짜 비표준** | BCE/AD, 다양한 포맷 혼재 |
| **연결 없음** | 인물↔사건↔장소 관계 미정립 |
| **임베딩 없음** | 벡터 검색 불가 |

---

## 해결 전략: 3단계 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│                    Alpha Data Pipeline                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Stage 1: EXTRACT]     [Stage 2: ENRICH]    [Stage 3: INDEX]  │
│                                                                 │
│   Raw Data ──────────► Structured ──────────► Searchable       │
│                         + Geocoded            + Embedded        │
│                         + Dated               + Linked          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: EXTRACT (추출)

### 1.1 Entity Extraction (개체 추출)

Wikipedia/텍스트에서 구조화된 개체 추출:

```python
# 추출 대상
entities = {
    "persons": {
        "name": str,
        "aliases": List[str],
        "birth_year": int,       # -490 = 490 BCE
        "death_year": int,
        "birth_place": str,
        "death_place": str,
        "occupation": List[str],
        "description": str,
    },
    "events": {
        "name": str,
        "year_start": int,
        "year_end": int,
        "location": str,
        "participants": List[str],
        "description": str,
        "category": str,         # war, treaty, discovery, etc.
    },
    "places": {
        "name": str,
        "aliases": List[str],
        "lat": float,
        "lng": float,
        "period_start": int,
        "period_end": int,
        "type": str,             # city, battlefield, temple, etc.
    }
}
```

### 1.2 Source-Specific Extractors

| Source | 추출 내용 | 난이도 |
|--------|----------|--------|
| **Pantheon** | 인물 59,902명 (날짜/직업 있음) | ⭐ 쉬움 |
| **Pleiades** | 장소 좌표 (이미 구조화) | ⭐ 쉬움 |
| **Wikidata** | 이벤트/인물 (이미 구조화) | ⭐ 쉬움 |
| **Atlas Academy** | FGO 서번트 (구조화됨) | ⭐ 쉬움 |
| **Theoi** | 그리스 신화 인물 | ⭐⭐ 보통 |
| **Wikipedia articles** | 인물/사건 추출 필요 | ⭐⭐⭐ 어려움 |
| **Gutenberg texts** | 본문에서 추출 필요 | ⭐⭐⭐⭐ 매우 어려움 |

### 1.3 Gutenberg 카탈로그 활용 (권장)

**LLM 없이 메타데이터로 추출:**

```python
# 카탈로그 필드 활용
catalog_fields = {
    "Authors": "Jefferson, Thomas, 1743-1826",  # 연도 추출 가능!
    "Subjects": "United States -- History",      # 시대/주제 매칭
    "LoCC": "E201",                              # 분류 코드
    "Bookshelves": "Harvard Classics",           # 컬렉션
}

# 저자 연도 정규식 추출 (71% 성공률)
import re
year_pattern = r'(\d{4})-(\d{4}|\?)'
# "Plato, 428-348 BCE" → (428, 348)
```

**비용: $0** (정규식만 사용)

### 1.4 LLM-Assisted Extraction (선택적)

카탈로그로 부족할 때만 사용:

```python
# 모델 정책
MODELS = {
    "classification": "gpt-5-nano",      # AI 분류/정리
    "final_response": "gpt-5.1-chat-latest",  # SHEBA 최종 응답
    # ❌ gpt-4o, gpt-4o-mini 사용 금지
}

extraction_prompt = """
Extract structured data from this historical text:
Text: {text}
Return JSON with:
- persons: [{name, birth_year, death_year, role}]
- events: [{name, year, location, description}]
"""
```

**비용 추정** (gpt-5-nano):
- 선별 1000개 텍스트: ~$5

---

## Stage 2: ENRICH (보강)

### 2.1 Geocoding (좌표 부여)

```python
geocoding_sources = [
    # Priority 1: 이미 있는 데이터
    "pleiades",      # 고대 장소 37,000개 좌표
    "topostext",     # 8,068개 고대 장소

    # Priority 2: 매칭
    "wikidata",      # SPARQL로 좌표 조회
    "geonames",      # 현대 지명 매칭

    # Priority 3: API (fallback)
    "nominatim",     # OpenStreetMap 무료 API
]
```

### 2.2 Date Normalization (날짜 정규화)

```python
# 통일 포맷: 정수 (음수 = BCE)
date_examples = {
    "490 BCE": -490,
    "490 BC": -490,
    "44 BC": -44,
    "476 AD": 476,
    "1453": 1453,
    "c. 500 BCE": -500,  # circa 처리
    "5th century BCE": -450,  # 세기 중앙값
}
```

### 2.3 Entity Linking (관계 연결)

```python
# 인물 ↔ 사건 ↔ 장소 연결
links = {
    "person_events": [
        {"person": "Alexander the Great", "event": "Battle of Gaugamela", "role": "commander"},
    ],
    "event_places": [
        {"event": "Battle of Gaugamela", "place": "Gaugamela", "lat": 36.56, "lng": 43.44},
    ],
    "person_places": [
        {"person": "Alexander the Great", "place": "Pella", "relation": "birthplace"},
    ],
}
```

---

## Stage 3: INDEX (색인)

### 3.1 Vector Embeddings

```python
embedding_config = {
    "model": "text-embedding-3-small",
    "chunk_size": 1000,      # tokens
    "chunk_overlap": 200,
    "batch_size": 100,

    # 임베딩 대상
    "targets": [
        "person.description",
        "event.description",
        "place.description",
        "text.content",      # Gutenberg 등 원문
    ]
}
```

**비용 추정**:
- 구조화 데이터: ~50M tokens → $1
- Gutenberg 청크: ~500M tokens → $10
- **총 임베딩 비용: ~$11**

### 3.2 Database Schema

```sql
-- 핵심 테이블
CREATE TABLE persons (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    name_ko TEXT,
    birth_year INT,
    death_year INT,
    birth_place_id INT REFERENCES places(id),
    occupation TEXT[],
    description TEXT,
    embedding vector(1536),
    sources JSONB,
    fgo_servant_id INT  -- FGO 연동
);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    name_ko TEXT,
    year_start INT NOT NULL,
    year_end INT,
    place_id INT REFERENCES places(id),
    category TEXT,
    description TEXT,
    embedding vector(1536),
    sources JSONB
);

CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    name_ko TEXT,
    lat FLOAT NOT NULL,
    lng FLOAT NOT NULL,
    period_start INT,
    period_end INT,
    place_type TEXT,
    pleiades_id TEXT,
    sources JSONB
);

-- 관계 테이블
CREATE TABLE person_events (
    person_id INT REFERENCES persons(id),
    event_id INT REFERENCES events(id),
    role TEXT
);
```

---

## 실행 계획

### Phase A: Quick Wins (1-2시간)

이미 구조화된 데이터 먼저 처리:

```bash
# 1. Pantheon 인물 임포트 (59,902명)
python scripts/import_pantheon.py

# 2. Pleiades 장소 임포트 (37,000개 좌표)
python scripts/import_pleiades.py

# 3. Wikidata 이벤트 임포트
python scripts/import_wikidata.py

# 4. Atlas Academy FGO 서번트 연동
python scripts/import_fgo_servants.py
```

**결과**: 지구본에 ~100,000개 포인트 표시 가능

### Phase B: Enrichment (2-4시간)

```bash
# 1. 장소명 → 좌표 매칭
python scripts/geocode_places.py

# 2. 날짜 정규화
python scripts/normalize_dates.py

# 3. 인물-사건-장소 연결
python scripts/link_entities.py
```

### Phase C: Embeddings (1-2시간)

```bash
# 1. 구조화 데이터 임베딩
python scripts/embed_entities.py

# 2. 텍스트 청킹 + 임베딩
python scripts/embed_texts.py --source gutenberg --limit 1000
```

### Phase D: Advanced Extraction (Optional)

```bash
# LLM으로 추가 추출 (비용 발생)
python scripts/llm_extract.py --source gutenberg --sample 100
```

---

## 예상 결과물

### Alpha v1 (Quick Wins 후)

| 데이터 | 수량 | 지구본 표시 |
|--------|------|------------|
| 인물 | ~60,000 | 출생지 마커 |
| 장소 | ~45,000 | 좌표 마커 |
| 이벤트 | ~5,000 | 시간+위치 |

### Alpha v2 (Full Pipeline 후)

| 데이터 | 수량 | 기능 |
|--------|------|------|
| 인물 | ~80,000 | 타임라인 + 관계망 |
| 장소 | ~50,000 | 시대별 필터 |
| 이벤트 | ~20,000 | 애니메이션 재생 |
| 텍스트 | ~10,000 | 시맨틱 검색 |

---

## 우선순위 추천

```
[즉시 실행] ─────────────────────────────────────────────────────
│
├─► Pantheon 임포트 (인물 60K, 좌표 있음)
├─► Pleiades 임포트 (장소 37K, 좌표 있음)
├─► Wikidata 임포트 (이벤트 5K)
│
[다음 단계] ─────────────────────────────────────────────────────
│
├─► FGO 서번트 ↔ 역사 인물 매칭
├─► 기본 임베딩 (구조화 데이터만)
│
[나중에] ────────────────────────────────────────────────────────
│
├─► Gutenberg 텍스트 임베딩 (선별)
├─► LLM 추출 (필요시)
└─► 추가 geocoding
```

---

## 필요한 스크립트

```
data/scripts/processing/
├── import_pantheon.py      # Pantheon → DB
├── import_pleiades.py      # Pleiades → DB
├── import_wikidata.py      # Wikidata → DB
├── import_fgo.py           # FGO 서번트 연동
├── geocode_places.py       # 장소 좌표 매칭
├── normalize_dates.py      # 날짜 정규화
├── link_entities.py        # 관계 연결
├── embed_entities.py       # 구조화 데이터 임베딩
└── embed_texts.py          # 텍스트 임베딩
```

---

## 요약

| 단계 | 시간 | 비용 | 결과 |
|------|------|------|------|
| Phase A | 1-2h | $0 | 지구본 기본 표시 |
| Phase B | 2-4h | $0 | 연결된 데이터 |
| Phase C | 1-2h | ~$11 | 검색 가능 |
| Phase D | 4h+ | ~$20+ | 고급 추출 |

**추천**: Phase A → B → C 순서로 진행. Phase D는 필요시.
