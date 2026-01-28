# 이벤트 계층화 (Event Hierarchy) - 인덱스

**작성일**: 2026-01-28
**목적**: 수천 개의 역사 이벤트를 의미 있는 계층 구조로 조직화

---

## 문서 목록

### 구조 설계
| 파일 | 내용 | 상태 |
|------|------|------|
| [00_OVERVIEW.md](./00_OVERVIEW.md) | 마스터 플랜, 전체 구조, 구현 일정 | 완료 |
| [01_SCHEMA.md](./01_SCHEMA.md) | DB 스키마 (계층 구조), Alembic 마이그레이션 | 완료 |
| [07_EVENT_RELATIONS.md](./07_EVENT_RELATIONS.md) | 이벤트 간 비계층 관계 (인과/영향) | 완료 |
| [08_VECTOR_MODEL.md](./08_VECTOR_MODEL.md) | 벡터 기반 역사 모델, 숨은 연결 발견 | 완료 |
| [09_RELATION_PIPELINE.md](./09_RELATION_PIPELINE.md) | Book Extractor 관계 후처리 파이프라인 | 완료 |
| [10_LOCATION_HIERARCHY.md](./10_LOCATION_HIERARCHY.md) | 장소 계층 구조 (future_plan 통합) | 완료 |
| [11_UNIFIED_MODEL.md](./11_UNIFIED_MODEL.md) | HistoricalUnit 통합 모델 (future_plan 통합) | 완료 |
| [12_PERIOD_EXTRACTION.md](./12_PERIOD_EXTRACTION.md) | Period/Era 추출 전략 (future_plan 통합) | 완료 |

### 카테고리별 이벤트 목록
| 파일 | 내용 | 상태 |
|------|------|------|
| [02_WARS.md](./02_WARS.md) | 전쟁/군사 분쟁 (BCE 3000 - 현재) | 완료 |
| [03_PHILOSOPHY.md](./03_PHILOSOPHY.md) | 철학 운동/학파 | 완료 |
| [04_ART_CULTURE.md](./04_ART_CULTURE.md) | 예술, 문학, 음악 운동 | 완료 |
| [05_SCIENCE.md](./05_SCIENCE.md) | 과학혁명, 기술 발전 | 완료 |
| [06_RELIGION.md](./06_RELIGION.md) | 종교 운동/사건 | 완료 |

---

## 계층 레벨 요약

| Level | 이름 | 설명 | 예시 |
|-------|------|------|------|
| 0 | Era | 시대 구분 | 고대, 중세, 근대 |
| 1 | Mega-Event | 대규모 역사적 흐름 | 로마 제국, 대항해시대 |
| 2 | Aggregate | 집합 이벤트 | 백년전쟁, 르네상스 |
| 3 | Major | 주요 개별 이벤트 | 아쟁쿠르 전투 |
| 4 | Minor | 세부 이벤트 | 소규모 조약, 회담 |

---

## Aggregate Type 분류

| Type | 설명 | 해당 문서 |
|------|------|----------|
| `war` | 전쟁/군사 분쟁 | 02_WARS.md |
| `movement` | 사회/문화 운동 | 04_ART_CULTURE.md |
| `dynasty` | 왕조/정권 시대 | 00_OVERVIEW.md |
| `expedition` | 탐험/원정 | 00_OVERVIEW.md |
| `revolution` | 혁명 | 00_OVERVIEW.md, 05_SCIENCE.md |
| `crisis` | 위기/재난 | 00_OVERVIEW.md |
| `artistic_period` | 예술 시대 | 04_ART_CULTURE.md |
| `philosophical_school` | 철학 학파/사조 | 03_PHILOSOPHY.md |
| `scientific_era` | 과학 시대 | 05_SCIENCE.md |
| `religious` | 종교 운동 | 06_RELIGION.md |

---

## 관계 유형 (기존 테이블 활용)

### 계층 관계 vs 연계 관계

| 유형 | 저장 위치 | 예시 |
|------|----------|------|
| **계층 (Hierarchy)** | `events.parent_event_id` | 백년전쟁 ⊃ 아쟁쿠르 전투 |
| **연계 (Relation)** | `event_relationships` 테이블 | 종교개혁 → 30년 전쟁 |

### event_relationships 타입

**기존 타입** (associations.py):
- `causes`, `follows`, `part_of`, `related_to`, `opposes`, `enables`, `prevents`

**추가 권장 타입**:
- `influenced`, `led_to`, `response_to`, `parallel`, `continuation`, `rivalry`, `synthesis`

### 모든 관계 테이블 (이미 존재!)

| 테이블 | 관계 | 문서 |
|--------|------|------|
| `event_relationships` | Event ↔ Event | 07_EVENT_RELATIONS.md |
| `person_relationships` | Person ↔ Person | (기존) |
| `location_relationships` | Location ↔ Location | (기존) |
| `polity_relationships` | Polity ↔ Polity | (기존) |

---

## 구현 순서 요약

### Phase 1: 스키마 & 기본 구조
1. Alembic 마이그레이션 생성 (01_SCHEMA.md 참조)
2. Event 모델 확장
3. 기본 API 수정

### Phase 2: 상위 이벤트 생성
1. 각 카테고리별 Aggregate 이벤트 DB 삽입
2. 기존 이벤트와 연결 스크립트 작성/실행

### Phase 3: 프론트엔드
1. 사이드바 트리 UI
2. 글로브 줌 기반 필터
3. 필터 패널 옵션 추가

### Phase 4: QA & 조정
1. 데이터 정합성 검증
2. UX 피드백 반영
3. 성능 최적화

---

## 빠른 참조

### DB 스키마 변경 (01_SCHEMA.md)

```python
class Event(Base):
    parent_event_id = Column(Integer, ForeignKey('events.id'))
    is_aggregate = Column(Boolean, default=False)
    hierarchy_level = Column(Integer, default=3)
    aggregate_type = Column(String(50))
    default_collapsed = Column(Boolean, default=False)
    min_zoom_level = Column(Float, default=1.0)
```

### API 변경 (00_OVERVIEW.md)

```
GET  /api/v1/events/hierarchy          # 계층적 이벤트 트리
GET  /api/v1/events/{id}/children      # 자식 이벤트들
GET  /api/v1/events/aggregates         # 상위 이벤트만
GET  /api/v1/events?hierarchy_level=2  # 레벨별 필터
```

---

## 데이터 입력 우선순위

### 우선순위 1 (핵심) - 먼저 구현
- 페르시아 전쟁, 펠로폰네소스 전쟁, 알렉산더 정복
- 포에니 전쟁, 십자군 전쟁, 백년전쟁
- 나폴레옹 전쟁, 세계대전
- 아테네 철학의 황금기, 계몽주의
- 르네상스, 과학혁명
- 초기 기독교, 이슬람의 탄생, 종교개혁

### 우선순위 2 (중요) - 2차 구현
- 로마 내전, 몽골 정복, 30년 전쟁
- 독일 관념론, 실존주의
- 바로크, 낭만주의, 인상주의
- 산업혁명, 정보기술혁명
- 대각성운동, 에큐메니칼 운동

### 우선순위 3 (보완) - 추후 확장
- 나머지 전쟁들
- 헬레니즘 철학, 스콜라 철학
- 모더니즘, 포스트모더니즘
- 생명공학, 원자력시대
- 동아시아 종교

---

## 참고 자료

### 일반
- [Wikipedia: List of Wars](https://en.wikipedia.org/wiki/List_of_wars)
- [World History Encyclopedia](https://www.worldhistory.org/)
- [Encyclopedia Britannica](https://www.britannica.com/)

### 철학
- [Stanford Encyclopedia of Philosophy](https://plato.stanford.edu/)
- [History of Philosophy without gaps](https://historyofphilosophy.net/)
- [Philosophy Basics](https://www.philosophybasics.com/)

### 예술/문화
- [Metropolitan Museum of Art Timeline](https://www.metmuseum.org/toah/)
- [Smarthistory](https://smarthistory.org/)
- [Oxford Music Online](https://www.oxfordmusiconline.com/)

### 과학
- [Science History Institute](https://www.sciencehistory.org/)
- [History of Science Society](https://hssonline.org/)

### 종교
- [BBC Religions](https://www.bbc.co.uk/religion/religions/)
- [Patheos](https://www.patheos.com/)
