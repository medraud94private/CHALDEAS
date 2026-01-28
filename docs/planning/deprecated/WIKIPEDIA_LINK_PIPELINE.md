# Wikipedia Link Pipeline

> **Status**: In Progress (Phase 1 구현 완료)
> **Date**: 2026-01-15
> **Related**: `WIKIDATA_PIPELINE.md`, `KIWIX_DATA_INTEGRATION.md`

---

## Overview

Wikipedia ZIM 파일에서 엔티티(인물/장소/이벤트)를 추출하고, DB와 매칭하여 Source로 등록하고, 문서 내 하이퍼링크를 통해 엔티티 간 관계를 구축하는 파이프라인.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 1: Extraction (구현 완료)                   │
│  wikipedia_en_nopic.zim (51GB) → persons/locations/events.jsonl     │
│  Script: kiwix_extract_all.py                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 2: DB Linking (구현 완료)                   │
│  JSONL → DB Match (QID/Name) → Source 생성 → 관계 등록              │
│  Script: link_wikipedia_to_db.py                                    │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 3: Chain Building (계획)                    │
│  Historical Chain 구성, API 연동                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Wikipedia Entity Extraction

### Script
`poc/scripts/kiwix_extract_all.py`

### Input
- `data/kiwix/wikipedia_en_nopic.zim` (51GB, 19,374,550 entries)

### Output Files
| File | Description |
|------|-------------|
| `poc/data/wikipedia_extract/persons.jsonl` | 추출된 인물 |
| `poc/data/wikipedia_extract/locations.jsonl` | 추출된 장소 |
| `poc/data/wikipedia_extract/events.jsonl` | 추출된 이벤트 |
| `poc/data/wikipedia_extract/checkpoint.json` | 진행 체크포인트 |

### Data Format

**persons.jsonl**
```json
{
  "title": "Napoleon",
  "qid": "Q517",
  "birth_year": 1769,
  "death_year": 1821,
  "summary": "Napoleon Bonaparte was a French military...",
  "path": "Napoleon"
}
```

**locations.jsonl**
```json
{
  "title": "Rome",
  "qid": "Q220",
  "latitude": 41.9,
  "longitude": 12.5,
  "summary": "Rome is the capital city of Italy...",
  "path": "Rome"
}
```

**events.jsonl**
```json
{
  "title": "Battle of Waterloo",
  "qid": "Q48314",
  "start_year": 1815,
  "end_year": 1815,
  "summary": "The Battle of Waterloo was fought on 18 June 1815...",
  "path": "Battle_of_Waterloo"
}
```

### Classification Rules

| Entity Type | Detection Criteria |
|-------------|-------------------|
| **Person** | `infobox biography/person/military person/...` 또는 `(년도-년도) + was a/an` 패턴 |
| **Location** | `coordinates + population` 또는 `infobox settlement/country` |
| **Event** | `belligerents + casualties` 또는 `infobox military conflict` 또는 `Battle of/War of/Siege of...` |

### Features
- **체크포인트**: 1,000개 스캔마다 저장 (중단 시 재개 가능)
- **파일 동기화**: 재시작 시 파일 라인 수와 체크포인트 자동 동기화
- **역사적 인물 필터**: 사망했거나 1925년 이전 출생 인물만 추출

### Usage
```bash
cd poc/scripts

# 전체 추출 (새로 시작)
python kiwix_extract_all.py --full

# 이어서 추출
python kiwix_extract_all.py --full --resume

# 상태 확인
python kiwix_extract_all.py --stats
```

### Progress (2026-01-15 23:00 기준)
```
Scanned: 4,869,000 / 19,374,550 (25.1%)
- persons:   23,412
- locations: 113,591
- events:    13,232
```

---

## Phase 2: DB Linking

### Script
`poc/scripts/link_wikipedia_to_db.py`

### Matching Strategy (정방향 + 역방향)

```
                    ┌─────────────────────┐
                    │  Wikipedia Entity   │
                    │  (from JSONL)       │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │ QID 매칭      │  │ 정확한 이름   │  │ ILIKE 이름    │
    │ (wikidata_id) │  │ (name =)      │  │ (대소문자무시) │
    └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
            │                  │                  │
            └──────────────────┴──────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  DB Entity Matched  │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┴─────────────────────┐
         ▼                                           ▼
┌─────────────────────┐                   ┌─────────────────────┐
│  Source 레코드 생성  │                   │  Entity-Source 연결 │
│  (Wikipedia 문서)   │                   │  (person_sources,   │
│                     │                   │   event_sources)    │
└─────────────────────┘                   └──────────┬──────────┘
                                                     │
                                                     ▼
                                          ┌─────────────────────┐
                                          │  내부 링크 추출      │
                                          │  (HTML parsing)     │
                                          └──────────┬──────────┘
                                                     │
                    ┌────────────────────────────────┼────────────────────────────────┐
                    ▼                                ▼                                ▼
          ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
          │ Person 문서에서  │              │ Event 문서에서   │              │ (향후) Source간  │
          │ Person 링크 발견 │              │ Person 링크 발견 │              │ 참조 관계        │
          └────────┬────────┘              └────────┬────────┘              └─────────────────┘
                   │                                │
                   ▼                                ▼
          ┌─────────────────┐              ┌─────────────────┐
          │ person_         │              │ event_persons   │
          │ relationships   │              │ (role:mentioned)│
          │ (mentioned_with)│              │                 │
          └─────────────────┘              └─────────────────┘
```

### Created/Updated Tables

| Table | Description | Fields |
|-------|-------------|--------|
| `sources` | Wikipedia 문서 Source | name, type, url, archive_type, document_path, title, language |
| `person_sources` | Person ↔ Source | person_id, source_id |
| `event_sources` | Event ↔ Source | event_id, source_id |
| `person_relationships` | Person ↔ Person | person_id, related_person_id, relationship_type, strength, confidence |
| `event_persons` | Event ↔ Person | event_id, person_id, role |

### Relationship Details

**person_relationships (Wikipedia 내부 링크 기반)**
| Field | Value | Note |
|-------|-------|------|
| relationship_type | `mentioned_with` | 같은 문서에 링크로 언급 |
| strength | 2 | 약한 관계 (1-5 스케일) |
| confidence | 0.5 | 링크만으로는 관계 성격 불확실 |

**event_persons (Wikipedia 내부 링크 기반)**
| Field | Value | Note |
|-------|-------|------|
| role | `mentioned` | 이벤트 문서에서 언급됨 |

### Entity Linking via Source Hyperlinks

Wikipedia Source 문서 내의 하이퍼링크를 통해 엔티티 간 관계를 구축:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Wikipedia "Napoleon" 문서 (Source)                                      │
│                                                                          │
│  원본 엔티티: DB Person "Napoleon"                                        │
│                                                                          │
│  내부 하이퍼링크:                                                         │
│    • "Josephine" → DB Person 매칭 → person_relationships 생성            │
│    • "Wellington" → DB Person 매칭 → person_relationships 생성           │
│    • "Battle of Austerlitz" → DB Event 매칭 → event_persons 생성         │
│    • "Paris" → DB Location 매칭 → (향후 구현)                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌─────────────────────┐         ┌─────────────────────┐
        │ person_relationships │         │ event_persons       │
        │                     │         │                     │
        │ Napoleon ↔ Josephine│         │ Austerlitz ↔ Napoleon│
        │ Napoleon ↔ Wellington│        │ (role: mentioned)   │
        │ (mentioned_with)    │         │                     │
        └─────────────────────┘         └─────────────────────┘
```

#### Case 1: Person 문서에서 Person 링크
```
Source: Wikipedia "Napoleon"
원본 엔티티: Person Napoleon (DB)
하이퍼링크: "Josephine" → Person Josephine (DB)

결과: person_relationships
  - person_id: Napoleon
  - related_person_id: Josephine
  - relationship_type: mentioned_with
  - strength: 2
```

#### Case 2: Person 문서에서 Event 링크
```
Source: Wikipedia "Napoleon"
원본 엔티티: Person Napoleon (DB)
하이퍼링크: "Battle of Austerlitz" → Event Austerlitz (DB)

결과: event_persons
  - event_id: Austerlitz
  - person_id: Napoleon
  - role: mentioned
```

#### Case 3: Event 문서에서 Person 링크
```
Source: Wikipedia "Battle of Waterloo"
원본 엔티티: Event Waterloo (DB)
하이퍼링크: "Napoleon", "Wellington" → Person (DB)

결과: event_persons
  - event_id: Waterloo
  - person_id: Napoleon (role: mentioned)
  - person_id: Wellington (role: mentioned)
```

#### 향후 구현: Location 연결
```
Source: Wikipedia "Napoleon"
하이퍼링크: "Paris" → Location Paris (DB)

결과: person_locations (테이블 필요) 또는 location_sources
```

### Usage
```bash
cd poc/scripts

# 전체 타입 링킹
python link_wikipedia_to_db.py --type all

# 특정 타입만
python link_wikipedia_to_db.py --type persons --limit 1000

# 이어서 링킹
python link_wikipedia_to_db.py --type all --resume

# 새로 시작
python link_wikipedia_to_db.py --type all --fresh

# 상태 확인
python link_wikipedia_to_db.py --stats
```

### Test Results (2026-01-15)
```
Processed: 500 persons
Matched:   30 (6%)
Sources:   11 created
Links:     0 (초기 알파벳순 데이터라 유명 인물 적음)
```

---

## Checkpoint System

### Files

| File | Purpose |
|------|---------|
| `poc/data/wikipedia_extract/checkpoint.json` | Extraction 진행 |
| `poc/data/wikipedia_extract/linker_checkpoint.json` | Linking 진행 |

### Extraction Checkpoint
```json
{
  "last_index": 4869000,
  "stats": {
    "scanned": 4869000,
    "persons": 23412,
    "locations": 113591,
    "events": 13232,
    "skipped_redirect": 2720796,
    "unclassified": 1849683
  }
}
```

### Linker Checkpoint
```json
{
  "persons": {
    "processed": 500,
    "matched": 30,
    "sources_created": 11,
    "links_created": 0
  },
  "locations": {...},
  "events": {...}
}
```

---

## Expected Results

### Extraction 완료 시 예상
| Type | Count |
|------|-------|
| Persons | ~200,000+ |
| Locations | ~500,000+ |
| Events | ~50,000+ |

### Linking 예상
| Metric | Estimate |
|--------|----------|
| 매칭률 (초기 알파벳순) | 2-5% |
| 매칭률 (후반 유명인물) | 10-20% |
| 매칭률 (전체 평균) | 5-10% |
| Source 레코드 | 수천 ~ 수만 |
| Person-Person 관계 | 매칭된 인물당 평균 5-10개 |
| Event-Person 관계 | 매칭된 이벤트당 평균 5-10개 |

---

## Implemented Link Types (2026-01-15 구현 완료)

| Source 타입 | 링크 대상 | 연결 테이블 | 상태 |
|-------------|----------|------------|------|
| Person 문서 | → Person 링크 | `person_relationships` | 구현 완료 |
| Person 문서 | → Event 링크 | `event_persons` | 구현 완료 |
| Event 문서 | → Person 링크 | `event_persons` | 구현 완료 |
| Event 문서 | → Event 링크 | `event_relationships` | 구현 완료 |
| Location 문서 | → Event 링크 | `event_locations` | 구현 완료 |
| Location 문서 | → Person 링크 | - | 미구현 (테이블 없음) |

---

## Known Limitations

1. **매칭률**: Wikipedia 알파벳 순서로 마이너 인물이 먼저 추출
2. **관계 정확도**: 내부 링크만으로는 관계의 성격(teacher, rival 등) 파악 불가
3. **Location-Person 연결**: `location_persons` 테이블 미존재
4. **Source 간 연결**: `source_references` 테이블 미존재

---

## Future Improvements

### 단기
- [ ] Location-Source 연결 테이블 추가
- [ ] Source 간 참조 관계 테이블 추가
- [ ] 매칭률 향상을 위한 alias 매칭

### 중기
- [ ] NER 기반 관계 성격 파악 (teacher, rival, ally 등)
- [ ] Wikidata에서 관계 정보 직접 가져오기
- [ ] 역방향 검색: DB → Wikipedia 매칭

### 장기
- [ ] Historical Chain 자동 생성
- [ ] 관계 강도 계산 (co-occurrence, 문서 내 거리)
- [ ] Frontend Chain 시각화

---

## Related Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `kiwix_extract_all.py` | Wikipedia 엔티티 추출 | 실행 중 (25%) |
| `link_wikipedia_to_db.py` | DB 링킹 + 관계 생성 | 구현 완료 |
| `kiwix_db_matcher.py` | 개별 매칭 유틸리티 | 구현 완료 |
| `kiwix_reader.py` | ZIM 파일 리더 | 구현 완료 |

---

## Open Questions

1. **DB에 없는 엔티티 처리**
   - 현재: QID만 저장하고 스킵
   - 향후: threshold 이상 언급된 것만 새로 생성?

2. **관계 강도 계산**
   - 현재: 고정값 (strength=2, confidence=0.5)
   - 향후: co-occurrence count 기반?

3. **중복 관계 처리**
   - 현재: 단방향 (A→B만 저장)
   - 향후: 양방향 통합 필요?
