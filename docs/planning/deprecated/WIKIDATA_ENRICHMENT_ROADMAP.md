# Wikidata/Wikipedia Enrichment Roadmap

> **Status**: In Progress
> **Date**: 2026-01-15
> **Related**: `WIKIDATA_PIPELINE.md`, `WIKIPEDIA_LINK_PIPELINE.md`, `DATA_PIPELINE_V2.md`

---

## Overview

Wikidata/Wikipedia를 활용한 데이터 보강 전체 로드맵.
기존 DATA_PIPELINE_V2.md의 Track A/B와 병행하여 진행.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WIKIDATA/WIKIPEDIA ENRICHMENT PIPELINE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Stage 1          Stage 2           Stage 3          Stage 4         Stage 5│
│  ┌──────┐        ┌──────┐          ┌──────┐        ┌──────┐        ┌──────┐│
│  │Entity│   →    │Wiki  │    →     │Entity│   →    │Relat-│   →    │Chain ││
│  │Match │        │Links │          │Expand│        │ionship│        │Build ││
│  └──────┘        └──────┘          └──────┘        └──────┘        └──────┘│
│    ↑               ↑                  ↑              ↑               ↑      │
│  현재 진행      Pilot 100명        새 엔티티       관계 생성      Historical│
│  (39%)          설계 완료          DB 추가                        Chain     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage Summary

| # | Stage | 문서 | 상태 | 예상 시간 |
|---|-------|------|------|----------|
| 1 | Entity Matching | [WIKIDATA_PIPELINE.md](./WIKIDATA_PIPELINE.md) | **In Progress** (39%) | ~8h remaining |
| 2 | Wikipedia Links | [WIKIPEDIA_LINK_PIPELINE.md](./WIKIPEDIA_LINK_PIPELINE.md) | Planning | ~2h (pilot) |
| 3 | Entity Expansion | [ENTITY_EXPANSION.md](./ENTITY_EXPANSION.md) | TODO | ~4h |
| 4 | Relationship Building | [RELATIONSHIP_BUILDING.md](./RELATIONSHIP_BUILDING.md) | TODO | ~2h |
| 5 | Historical Chain | [HISTORICAL_CHAIN_IMPL.md](./HISTORICAL_CHAIN_IMPL.md) | TODO | ~4h |

---

## Stage 1: Entity Matching (현재 진행 중)

**목표**: DB 인물에 Wikidata QID 매칭

### Progress
| Metric | Value |
|--------|-------|
| DB 전체 인물 | 286,609 |
| 현재 매칭됨 | 33,631 (11.73%) |
| Forward 진행 | 111,404 / 285,652 (39%) |

### Checklist
- [x] Forward matching 스크립트 (`wikidata_reconcile.py`)
- [x] Reverse matching 완료 (10,331명 수집, 4,905 매칭)
- [ ] Forward matching 전체 완료
- [ ] Reverse 결과 DB 적용
- [ ] Forward 결과 DB 적용

### 예상 완료 후 상태
- wikidata_id 보유 인물: **~100,000명** (추정)

---

## Stage 2: Wikipedia Link Collection

**목표**: 매칭된 인물의 Wikipedia 문서에서 관련 엔티티 링크 수집

### Approach
1. 주요 인물 100명 선정 (Pilot)
2. Wikipedia API로 각 인물 문서의 outgoing links 수집
3. 각 링크의 Wikidata QID 확인
4. QID 타입 분류 (인물/사건/장소)

### Output
```json
{
  "person_id": 123,
  "wikidata_qid": "Q1048",
  "wikipedia_links": {
    "persons": ["Q1001", "Q2044", ...],
    "events": ["Q182598", "Q192830", ...],
    "locations": ["Q220", "Q17", ...]
  }
}
```

### Checklist
- [ ] `select_pilot_persons.py` - 파일럿 100명 선정
- [ ] `fetch_wikipedia_links.py` - 링크 수집
- [ ] `classify_link_types.py` - 타입 분류
- [ ] 결과 JSON 저장

---

## Stage 3: Entity Expansion

**목표**: Wikipedia에서 발견된 새 엔티티를 DB에 추가

### 발견될 엔티티 유형
| Type | 예상 수량 | 처리 방식 |
|------|----------|----------|
| 인물 (Q5) | ~5,000+ | DB persons 테이블 추가 |
| 사건 | ~2,000+ | DB events 테이블 추가 |
| 장소 | ~1,000+ | DB locations 테이블 추가 |

### Decision Points
1. **어떤 엔티티를 추가할 것인가?**
   - 옵션 A: 모든 발견된 엔티티
   - 옵션 B: N회 이상 언급된 것만
   - 옵션 C: 특정 카테고리만 (역사적 중요도)

2. **메타데이터 수집 범위**
   - 기본: QID, 이름, 타입
   - 확장: 생몰년, 설명, 이미지, Wikipedia URL

### Checklist
- [ ] 추가 기준 결정
- [ ] `expand_entities_from_wiki.py` - 새 엔티티 생성
- [ ] Wikidata에서 메타데이터 fetch
- [ ] DB에 bulk insert

---

## Stage 4: Relationship Building

**목표**: 발견된 연결을 relationship 테이블에 저장

### Relationship Types
| Type | Subject | Object | Example |
|------|---------|--------|---------|
| `mentioned_with` | Person | Person | Caesar ↔ Pompey |
| `participated_in` | Person | Event | Caesar → Gallic Wars |
| `occurred_at` | Event | Location | Gallic Wars → Gaul |
| `born_in` | Person | Location | Caesar → Rome |
| `died_in` | Person | Location | Caesar → Rome |

### Schema
```sql
-- 인물-인물 관계
CREATE TABLE person_person_links (
    source_person_id INT,
    target_person_id INT,
    target_qid VARCHAR(20),
    relationship_type VARCHAR(50),
    source_article VARCHAR(255),
    confidence FLOAT,
    PRIMARY KEY (source_person_id, target_person_id)
);

-- 인물-사건 관계
CREATE TABLE person_event_links (
    person_id INT,
    event_id INT,
    event_qid VARCHAR(20),
    relationship_type VARCHAR(50),
    confidence FLOAT,
    PRIMARY KEY (person_id, COALESCE(event_id, 0))
);
```

### Checklist
- [ ] DB 마이그레이션 (새 테이블)
- [ ] `create_relationships.py` - 관계 생성
- [ ] 중복 처리 로직
- [ ] 양방향 관계 처리

---

## Stage 5: Historical Chain Construction

**목표**: 관계 데이터를 기반으로 Historical Chain 생성

### Chain Types
1. **Person Story Chain**: 인물 중심
   ```
   Caesar 탄생 → 갈리아 정복 → 루비콘 도하 → 내전 → 암살
   ```

2. **Event Chain**: 사건 인과관계
   ```
   마케도니아 헤게모니 → 알렉산더 정복 → 헬레니즘 시대
   ```

3. **Era Story**: 시대 종합
   ```
   로마 공화정 말기: 주요 인물들, 사건들, 장소들
   ```

### Implementation
```python
def build_person_chain(person_id: int, depth: int = 2):
    """
    인물 중심 체인 구성
    1. 해당 인물의 참여 이벤트 조회
    2. 이벤트들의 다른 참여자 조회
    3. 시간순 정렬
    4. Chain 구조로 반환
    """
    pass
```

### API Endpoint
```
GET /api/v1/chain/person/{person_id}
GET /api/v1/chain/event/{event_id}
GET /api/v1/chain/era/{era_name}
```

### Checklist
- [ ] Chain 빌더 로직 구현
- [ ] API endpoint 추가
- [ ] Frontend Timeline 연동
- [ ] 캐싱 전략 (자주 요청되는 체인)

---

## Execution Order

```
Today (01-15):
├─ Stage 1 계속 (Reconcile 50k 배치)
└─ Stage 2 설계 완료

Next:
├─ Stage 1 완료 → DB 적용
├─ Stage 2 Pilot 실행 (100명)
├─ Stage 3-4 설계
└─ Stage 5 설계

Later:
├─ Stage 2 확장 (전체)
├─ Stage 3-4 실행
└─ Stage 5 구현
```

---

## Dependencies

```
Stage 1 (Matching) ────────────────────────────────────┐
                                                       │
                                                       ▼
Stage 2 (Wiki Links) ─────── requires QID ────────────────────────┐
                                                                   │
Stage 3 (Expansion) ─────── requires Stage 2 output ───────────────┤
                                                                   │
Stage 4 (Relationships) ── requires Stage 2 & 3 ───────────────────┤
                                                                   │
Stage 5 (Chain) ────────── requires Stage 4 ───────────────────────┘
```

---

## Quick Commands

```bash
# Stage 1: Resume matching
python poc/scripts/wikidata_reconcile.py --resume --limit 50000

# Stage 1: Apply reverse matches
python poc/scripts/apply_reverse_wikidata.py --dry-run

# Stage 2 (TBD):
python poc/scripts/select_pilot_persons.py
python poc/scripts/fetch_wikipedia_links.py --limit 100

# Check DB status
cd backend && python -c "
from app.db.session import SessionLocal
from app.models.person import Person
db = SessionLocal()
print('With wikidata:', db.query(Person).filter(Person.wikidata_id.isnot(None)).count())
"
```

---

## Related Documents

- [WIKIDATA_PIPELINE.md](./WIKIDATA_PIPELINE.md) - Stage 1 상세
- [WIKIPEDIA_LINK_PIPELINE.md](./WIKIPEDIA_LINK_PIPELINE.md) - Stage 2 상세
- [DATA_PIPELINE_V2.md](./DATA_PIPELINE_V2.md) - 전체 데이터 파이프라인 (Track A/B)
- [HISTORICAL_CHAIN_CONCEPT.md](./completed/HISTORICAL_CHAIN_CONCEPT.md) - Historical Chain 컨셉
