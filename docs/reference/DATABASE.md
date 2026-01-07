# Database Schema

## 구현 상태: V0 완료 / V1 스키마 추가 (2026-01-07)

> **V1 업데이트**: Historical Chain 및 Batch NER 555K 엔티티 지원을 위한 스키마 확장 완료

## ER Diagram

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────┐
│  Category   │◄──────│      Event      │───────►│  Location   │
├─────────────┤       ├─────────────────┤       ├─────────────┤
│ id          │       │ id              │       │ id          │
│ name        │       │ title           │       │ name        │
│ name_ko     │       │ title_ko        │       │ name_ko     │
│ slug        │       │ description     │       │ latitude    │
│ color       │       │ date_start (*)  │       │ longitude   │
│ parent_id   │       │ date_end        │       │ type        │
└─────────────┘       │ importance      │       │ modern_name │
                      │ category_id     │       └─────────────┘
                      │ location_id     │
                      └────────┬────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       event_persons    event_locations   event_sources
              │                │                │
              ▼                ▼                ▼
        ┌─────────┐      ┌─────────┐      ┌─────────┐
        │ Person  │      │Location │      │ Source  │
        └─────────┘      └─────────┘      └─────────┘
```

## 핵심 테이블

### events
역사적 사건을 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| title | VARCHAR(500) | 영문 제목 |
| title_ko | VARCHAR(500) | 한국어 제목 |
| slug | VARCHAR(500) | URL용 슬러그 |
| date_start | INTEGER | 시작 연도 (음수 = BCE) |
| date_end | INTEGER | 종료 연도 |
| date_precision | VARCHAR(20) | exact/year/decade/century |
| importance | INTEGER | 중요도 (1-5) |
| category_id | FK | 카테고리 참조 |
| primary_location_id | FK | 주요 장소 참조 |

### persons
역사적 인물을 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 영문 이름 |
| name_ko | VARCHAR(255) | 한국어 이름 |
| birth_year | INTEGER | 출생 연도 (음수 = BCE) |
| death_year | INTEGER | 사망 연도 |
| biography | TEXT | 약력 |
| category_id | FK | 카테고리 참조 |
| birthplace_id | FK | 출생지 참조 |

### locations
지리적 장소를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 고대 지명 |
| name_ko | VARCHAR(255) | 한국어 지명 |
| latitude | DECIMAL(10,8) | 위도 |
| longitude | DECIMAL(11,8) | 경도 |
| type | VARCHAR(50) | city/region/landmark |
| modern_name | VARCHAR(255) | 현대 지명 |

### sources
출처 정보를 저장합니다 (LAPLACE용).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 출처명 |
| type | VARCHAR(50) | primary/secondary/digital_archive |
| url | VARCHAR(500) | URL |
| archive_type | VARCHAR(50) | perseus/ctext/gutenberg 등 |
| reliability | INTEGER | 신뢰도 (1-5) |

## BCE 날짜 처리

- 내부적으로 음수로 저장 (490 BCE → -490)
- 표시 시 변환: `date_display` property 사용

```python
# 예시
event.date_start = -490  # 490 BCE
event.date_display  # "490 BCE"
```

## 구현 파일

- `backend/app/models/event.py`
- `backend/app/models/person.py`
- `backend/app/models/location.py`
- `backend/app/models/source.py`
- `backend/app/models/category.py`
- `backend/app/models/associations.py`

---

# V1 스키마 확장 (2026-01-07)

## V1 ER Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              HISTORICAL CHAIN SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   ┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐      │
│   │   Period    │◄────────│ HistoricalChain  │────────►│  ChainSegment   │      │
│   ├─────────────┤         ├──────────────────┤         ├─────────────────┤      │
│   │ id          │         │ id               │         │ id              │      │
│   │ name        │         │ chain_type (*)   │         │ chain_id        │      │
│   │ year_start  │         │ focal_person_id  │         │ sequence_number │      │
│   │ year_end    │         │ focal_location_id│         │ narrative       │      │
│   │ parent_id   │         │ focal_period_id  │         │ transition_type │      │
│   │ temporal_   │         │ focal_event_id   │         │ importance      │      │
│   │   scale     │         │ status           │         └────────┬────────┘      │
│   └─────────────┘         │ access_count     │                  │               │
│                           └──────────────────┘                  ▼               │
│                                                        ┌─────────────────┐      │
│   ┌─────────────┐         chain_type:                  │ChainEntityRole  │      │
│   │   Polity    │         • person_story               ├─────────────────┤      │
│   ├─────────────┤         • place_story                │ segment_id      │      │
│   │ id          │         • era_story                  │ entity_type     │      │
│   │ name        │         • causal_chain               │ entity_id       │      │
│   │ polity_type │                                      │ role            │      │
│   │ predecessor │                                      └─────────────────┘      │
│   │ successor   │                                                               │
│   │ start_year  │                                                               │
│   └─────────────┘                                                               │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              NER EXTRACTION TRACKING                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   ┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐      │
│   │ ImportBatch │◄────────│   TextMention    │────────►│  EntityAlias    │      │
│   ├─────────────┤         ├──────────────────┤         ├─────────────────┤      │
│   │ id          │         │ id               │         │ id              │      │
│   │ batch_name  │         │ entity_type      │         │ entity_type     │      │
│   │ source_type │         │ entity_id        │         │ entity_id       │      │
│   │ status      │         │ source_id        │         │ alias           │      │
│   │ total_items │         │ mention_text     │         │ alias_type      │      │
│   │ started_at  │         │ confidence       │         │ language        │      │
│   │ completed_at│         │ extraction_model │         └─────────────────┘      │
│   └─────────────┘         └──────────────────┘                                   │
│                                                                                   │
│   ┌───────────────────┐                                                          │
│   │  PendingEntity    │   status: unprocessed → matched → created → rejected    │
│   ├───────────────────┤                                                          │
│   │ id                │                                                          │
│   │ entity_type       │                                                          │
│   │ raw_data          │                                                          │
│   │ match_candidates  │                                                          │
│   │ status            │                                                          │
│   └───────────────────┘                                                          │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## V1 신규 테이블

### periods
시대/기간을 저장합니다 (Braudel의 시간 척도 지원).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 시대명 (영문) |
| name_ko | VARCHAR(255) | 시대명 (한국어) |
| slug | VARCHAR(255) | URL 슬러그 (UNIQUE) |
| year_start | INTEGER | 시작 연도 (음수 = BCE) |
| year_end | INTEGER | 종료 연도 |
| temporal_scale | VARCHAR(20) | evenementielle/conjuncture/longue_duree |
| parent_id | FK | 상위 시대 참조 (계층 구조) |
| confidence | FLOAT | NER 추출 신뢰도 |
| is_manual_curated | BOOLEAN | 수동 큐레이션 여부 |

### polities
정치 단체 (제국, 왕국, 왕조 등)를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| name | VARCHAR(255) | 명칭 |
| slug | VARCHAR(255) | URL 슬러그 (UNIQUE) |
| polity_type | VARCHAR(50) | empire/kingdom/republic/dynasty/city_state/tribe |
| start_year | INTEGER | 시작 연도 |
| end_year | INTEGER | 종료 연도 |
| capital_id | FK | 수도 Location 참조 |
| predecessor_id | FK | 선행 정치체 |
| successor_id | FK | 후행 정치체 |
| certainty | VARCHAR(20) | fact/probable/legendary/mythological |
| embedding | VECTOR(1536) | 벡터 임베딩 (pgvector) |

### historical_chains
역사의 고리 (4가지 큐레이션 유형)를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| chain_type | VARCHAR(20) | person_story/place_story/era_story/causal_chain |
| slug | VARCHAR(255) | URL 슬러그 (UNIQUE) |
| title | VARCHAR(500) | 제목 |
| summary | TEXT | 요약 |
| focal_person_id | FK | Person Story용 인물 |
| focal_location_id | FK | Place Story용 장소 |
| focal_period_id | FK | Era Story용 시대 |
| focal_event_id | FK | Causal Chain용 핵심 사건 |
| year_start | INTEGER | 시작 연도 |
| year_end | INTEGER | 종료 연도 |
| status | VARCHAR(20) | user/cached/featured/system (승격 시스템) |
| access_count | INTEGER | 조회 수 |
| is_auto_generated | BOOLEAN | AI 자동 생성 여부 |
| quality_score | FLOAT | 품질 점수 |

### chain_segments
체인의 개별 세그먼트를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| chain_id | FK | HistoricalChain 참조 |
| sequence_number | INTEGER | 순서 번호 |
| title | VARCHAR(500) | 세그먼트 제목 |
| narrative | TEXT | AI 생성 내러티브 |
| transition_type | VARCHAR(30) | causes/follows/parallel/consequence |
| transition_strength | INTEGER | 연결 강도 (1-5) |
| importance | INTEGER | 중요도 (1-5) |
| is_keystone | BOOLEAN | 핵심 세그먼트 여부 |

### text_mentions
NER 추출 출처를 추적합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| entity_type | VARCHAR(50) | person/location/event/polity/period |
| entity_id | INTEGER | 엔티티 ID |
| source_id | FK | Source 참조 |
| mention_text | VARCHAR(500) | 언급 텍스트 |
| context_text | TEXT | 문맥 |
| confidence | FLOAT | 추출 신뢰도 |
| extraction_model | VARCHAR(100) | 추출 모델 (gpt-5-nano, spacy 등) |

### entity_aliases
엔티티 별칭 (중복 제거용)을 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| entity_type | VARCHAR(50) | person/location/event |
| entity_id | INTEGER | 정규 엔티티 ID |
| alias | VARCHAR(500) | 별칭 |
| alias_type | VARCHAR(50) | alternate/translation/misspelling/historical |
| language | VARCHAR(10) | en/ko/la/gr 등 |

### import_batches
배치 임포트를 추적합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| batch_name | VARCHAR(255) | 배치 이름 |
| source_type | VARCHAR(100) | 소스 유형 |
| status | VARCHAR(20) | pending/processing/completed/failed |
| total_items | INTEGER | 전체 항목 수 |
| successful_items | INTEGER | 성공 항목 수 |
| failed_items | INTEGER | 실패 항목 수 |
| started_at | TIMESTAMP | 시작 시간 |
| completed_at | TIMESTAMP | 완료 시간 |

## V1 확장된 기존 테이블

### persons (확장)

| 추가 컬럼 | 타입 | 설명 |
|----------|------|------|
| canonical_id | FK | 정규 인물 참조 (중복 제거) |
| role | VARCHAR(255) | 역할 (king, philosopher 등) |
| era | VARCHAR(100) | 시대 (Classical, Medieval 등) |
| floruit_start | INTEGER | 활동 시작 연도 (fl. 표기) |
| floruit_end | INTEGER | 활동 종료 연도 |
| certainty | VARCHAR(20) | fact/probable/legendary/mythological |
| embedding | VECTOR(1536) | 벡터 임베딩 |
| primary_polity_id | FK | 소속 정치체 |
| mention_count | INTEGER | 언급 횟수 |
| avg_confidence | FLOAT | 평균 신뢰도 |

### sources (확장)

| 추가 컬럼 | 타입 | 설명 |
|----------|------|------|
| document_id | VARCHAR(255) | 원본 문서 ID |
| document_path | VARCHAR(500) | 파일 경로 |
| title | VARCHAR(500) | 문서 제목 |
| original_year | INTEGER | 원본 작성 연도 |
| language | VARCHAR(10) | 언어 코드 |

### events (확장)

| 추가 컬럼 | 타입 | 설명 |
|----------|------|------|
| temporal_scale | VARCHAR(20) | evenementielle/conjuncture/longue_duree |
| period_id | FK | Period 참조 |
| certainty | VARCHAR(20) | fact/probable/legendary/mythological |

## V1 성능 인덱스

```sql
-- 시간 범위 쿼리 (Historical Chain 생성)
CREATE INDEX idx_events_temporal_range ON events(date_start, date_end);
CREATE INDEX idx_events_period_date ON events(period_id, date_start);

-- Person Story 쿼리
CREATE INDEX idx_event_persons_person ON event_persons(person_id);

-- Place Story 쿼리
CREATE INDEX idx_event_locations_location ON event_locations(location_id);

-- Causal Chain 쿼리
CREATE INDEX idx_event_rel_causal ON event_relationships(from_event_id, relationship_type);
```

## V1 마이그레이션

```bash
# 마이그레이션 실행
cd backend
python -m alembic upgrade head

# 현재 버전 확인
python -m alembic current
```

마이그레이션 파일: `backend/alembic/versions/001_v1_schema_initial.py`

## V1 구현 파일

**신규 모델:**
- `backend/app/models/v1/period.py`
- `backend/app/models/v1/polity.py`
- `backend/app/models/v1/chain.py`
- `backend/app/models/v1/text_mention.py`

**확장된 모델:**
- `backend/app/models/person.py` (V1 필드 추가)
- `backend/app/models/source.py` (V1 필드 추가)
- `backend/app/models/event.py` (V1 필드 추가)
- `backend/app/models/associations.py` (관계 테이블 확장)
