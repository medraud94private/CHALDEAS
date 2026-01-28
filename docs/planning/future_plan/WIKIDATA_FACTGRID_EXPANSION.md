# Wikidata/FactGrid 역방향 확장 방법론

**Date**: 2026-01-13
**Status**: Planning
**Author**: Claude + User

---

## 0. 핵심 아이디어

### 가져올 데이터
```
Wikidata
├── 역사적 인물 (Person) → persons 테이블
│   └── Wikipedia 문서 → sources 테이블
├── 인물 관련 이벤트 (Event) → events 테이블
│   └── Wikipedia 문서 → sources 테이블
└── 관계 데이터 → person_events, relationships 테이블
```

### 신뢰도 체계
```
┌─────────────────────────────────────────────────────────────┐
│                    데이터 신뢰도 등급                         │
├─────────────────────────────────────────────────────────────┤
│ VERIFIED      │ Wikidata 검증됨, wikidata_id 있음            │
│ SOURCED       │ 출처 명확함 (Wikipedia 등)                   │
│ EXTRACTED     │ NER로 추출됨, 미검증                         │
│ NOISE         │ 노이즈 데이터 (Mrs. Perry 등)                │
└─────────────────────────────────────────────────────────────┘
```

### 중복 인물 통합
```
canonical_id 활용:
- "Aristotle" (id: 100, wikidata: Q868)  ← canonical
- "아리스토텔레스" (id: 200, canonical_id: 100)
- "Aristoteles" (id: 300, canonical_id: 100)
```

---

## 1. 현재 상황

### 데이터 품질 문제

| 항목 | 값 |
|------|-----|
| 전체 persons | 285,750 |
| 노이즈 제외 후 | 267,219 |
| 생몰년 있음 | 75,180 (26%) |
| wikidata_id 있음 | 759 (0.3%) |

### 기존 접근법의 한계 (순방향)

```
우리 DB persons → Wikidata 검색 → 매칭 시도
                                    ↓
                              0.2% 성공률
```

**문제점**:
- NER에서 추출한 저품질 데이터가 대부분
- "Mrs. Perry", "Miss Daniel" 같은 노이즈
- 생몰년 없는 인물은 매칭 검증 불가
- Wikidata API 호출 횟수 낭비

---

## 2. 역방향 접근법 (제안)

### 개념

```
Wikidata/FactGrid에서 역사인물 목록 가져오기
           ↓
    우리 DB와 매칭 시도
           ↓
    ┌──────┴──────┐
    ↓             ↓
매칭됨          새 인물
(enrichment)   (import)
```

### 장점

1. **고품질 데이터 보장**: Wikidata/FactGrid의 인물은 이미 검증됨
2. **풍부한 메타데이터**: 생몰년, 직업, 위키피디아 링크 등 함께 제공
3. **효율적**: 필요한 인물만 선별해서 가져옴
4. **관계 데이터**: 인물 간 관계 (사제, 친족 등) 포함 가능

---

## 3. 데이터 소스

### 3.1 Wikidata

**역사 인물 쿼리 예시**:
```sparql
SELECT ?person ?personLabel ?birth ?death ?occupation
WHERE {
  ?person wdt:P31 wd:Q5 .           # instance of human
  ?person wdt:P106 ?occupation .     # has occupation
  ?occupation wdt:P279* wd:Q4164871 . # subclass of position

  OPTIONAL { ?person wdt:P569 ?birth . }
  OPTIONAL { ?person wdt:P570 ?death . }

  # 역사적 인물 (1900년 이전 출생)
  FILTER (YEAR(?birth) < 1900)

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ko" . }
}
LIMIT 10000
```

**카테고리별 쿼리**:
- 군주/통치자: `wdt:P106 wd:Q116`
- 철학자: `wdt:P106 wd:Q4964182`
- 장군/군인: `wdt:P106 wd:Q47064`
- 예술가: `wdt:P106 wd:Q483501`
- 종교인: `wdt:P106 wd:Q2259532`

### 3.2 FactGrid

[FactGrid](https://database.factgrid.de/)는 역사학 전문 Knowledge Base.

**장점**:
- 역사 연구에 특화
- 학술적 검증된 데이터
- Wikidata와 연결됨 (P1 property)

**SPARQL Endpoint**: `https://database.factgrid.de/sparql`

**예시 쿼리**:
```sparql
PREFIX fg: <https://database.factgrid.de/entity/>
PREFIX fgp: <https://database.factgrid.de/prop/direct/>

SELECT ?person ?personLabel ?wikidata
WHERE {
  ?person fgp:P2 fg:Q7 .  # instance of human
  OPTIONAL { ?person fgp:P1 ?wikidata . }  # Wikidata ID
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 1000
```

---

## 4. 매칭 전략

### 4.1 단계별 매칭

```
Step 1: wikidata_id 직접 매칭 (우리 DB에 이미 있는 759명)
        ↓
Step 2: 이름 + 생몰년 정확 매칭
        ↓
Step 3: 이름 유사도 + 생몰년 범위 매칭
        ↓
Step 4: 매칭 안 된 인물은 새로 추가 (선택적)
```

### 4.2 매칭 스코어링

```python
def calculate_match_score(wikidata_person, db_person):
    score = 0

    # 이름 매칭 (최대 50점)
    name_sim = fuzzy_ratio(wikidata_person.name, db_person.name)
    score += name_sim * 0.5

    # 생몰년 매칭 (최대 40점)
    if wikidata_person.birth_year and db_person.birth_year:
        if wikidata_person.birth_year == db_person.birth_year:
            score += 20
        elif abs(wikidata_person.birth_year - db_person.birth_year) <= 5:
            score += 10

    if wikidata_person.death_year and db_person.death_year:
        if wikidata_person.death_year == db_person.death_year:
            score += 20
        elif abs(wikidata_person.death_year - db_person.death_year) <= 5:
            score += 10

    # 직업/역할 매칭 (최대 10점)
    if occupation_overlap(wikidata_person, db_person):
        score += 10

    return score
```

### 4.3 임계값

| 점수 | 액션 |
|------|------|
| >= 90 | 자동 매칭 |
| 70-89 | 수동 검토 |
| < 70 | 새 인물로 추가 (선택적) |

---

## 5. 가져올 데이터 필드

### Wikidata에서 가져올 수 있는 정보

| Property | Wikidata ID | 설명 |
|----------|-------------|------|
| 이름 | rdfs:label | 다국어 이름 |
| 생년 | P569 | Date of birth |
| 몰년 | P570 | Date of death |
| 출생지 | P19 | Place of birth |
| 사망지 | P20 | Place of death |
| 직업 | P106 | Occupation |
| 국적 | P27 | Country of citizenship |
| 이미지 | P18 | Image |
| 위키피디아 | sitelink | Wikipedia URL |
| 설명 | schema:description | 짧은 설명 |

### DB 업데이트 대상 컬럼

```python
person.wikidata_id = qid
person.name = label_en
person.name_ko = label_ko
person.birth_year = birth_year
person.death_year = death_year
person.birthplace_id = get_or_create_location(birthplace)
person.deathplace_id = get_or_create_location(deathplace)
person.image_url = image_url
person.wikipedia_url = wikipedia_url
person.biography = description
```

---

## 6. 구현 계획

### Phase 1: Wikidata에서 역사 인물 가져오기

```bash
# 스크립트: poc/scripts/fetch_wikidata_persons.py
python poc/scripts/fetch_wikidata_persons.py \
    --category philosophers \
    --year-before 1900 \
    --limit 5000 \
    --output poc/data/wikidata_philosophers.json
```

**카테고리별 예상 인물 수**:
- 철학자: ~5,000
- 군주/통치자: ~20,000
- 군인/장군: ~15,000
- 예술가: ~30,000
- 종교인: ~10,000
- **합계**: ~80,000 (중복 제외 시 ~50,000 예상)

### Phase 2: DB 매칭

```bash
python poc/scripts/match_wikidata_to_db.py \
    --input poc/data/wikidata_philosophers.json \
    --threshold 70 \
    --output poc/data/wikidata_matches_philosophers.json
```

### Phase 3: Enrichment 적용

```bash
python poc/scripts/apply_wikidata_enrichment.py \
    --input poc/data/wikidata_matches_philosophers.json \
    --update-fields name_ko,birth_year,death_year,image_url
```

### Phase 4: 새 인물 Import (선택적)

```bash
python poc/scripts/import_wikidata_persons.py \
    --input poc/data/wikidata_philosophers.json \
    --only-unmatched \
    --min-importance 1000  # sitelink 수 기준
```

---

## 7. FactGrid 활용

### 언제 사용?

- 특정 시대/지역 연구 시 (예: 중세 유럽)
- 학술적 정확성이 중요할 때
- Wikidata에 없는 인물 찾을 때

### 워크플로우

```
FactGrid 쿼리 → Wikidata ID 추출 → Wikidata에서 상세 정보 가져오기
```

---

## 8. 예상 결과

### Before (현재)
- wikidata_id 있음: 759명 (0.3%)
- 고품질 데이터: ~70,000명

### After (예상)
- wikidata_id 있음: ~50,000명 (18%)
- enriched 데이터: 생몰년, 이미지, 위키피디아 링크 등

---

## 9. 리스크 및 고려사항

### API 제한
- Wikidata SPARQL: 1분당 제한 있음
- 대량 쿼리 시 배치 처리 필요

### 데이터 충돌
- 우리 DB와 Wikidata 정보가 다를 경우?
- → Wikidata 우선, 원본 보존 (별도 컬럼)

### 중복 인물
- 동명이인 처리
- → 생몰년 + 직업으로 구분

---

## 10. DB 스키마 변경 필요

### Person 테이블 추가 필드

```sql
ALTER TABLE persons ADD COLUMN IF NOT EXISTS data_quality VARCHAR(20) DEFAULT 'extracted';
-- ENUM: verified, sourced, extracted, noise

ALTER TABLE persons ADD COLUMN IF NOT EXISTS source_type VARCHAR(20) DEFAULT 'ner';
-- ENUM: wikidata, wikipedia, ner, manual

ALTER TABLE persons ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
-- Wikidata 검증 시점

COMMENT ON COLUMN persons.data_quality IS '데이터 품질: verified(Wikidata검증), sourced(출처명확), extracted(NER추출), noise(노이즈)';
COMMENT ON COLUMN persons.canonical_id IS '중복 인물 통합용 - 대표 인물 ID 참조';
```

### Sources 테이블 (Wikipedia 문서용)

```sql
-- 이미 있을 수 있음, 확인 필요
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(50),  -- wikipedia, wikidata, book, article
    url VARCHAR(1000),
    wikidata_id VARCHAR(50),
    language VARCHAR(10) DEFAULT 'en',
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS person_sources (
    person_id INT REFERENCES persons(id),
    source_id INT REFERENCES sources(id),
    PRIMARY KEY (person_id, source_id)
);

CREATE TABLE IF NOT EXISTS event_sources (
    event_id INT REFERENCES events(id),
    source_id INT REFERENCES sources(id),
    PRIMARY KEY (event_id, source_id)
);
```

---

## 11. Wikidata에서 이벤트 가져오기

### SPARQL 쿼리 예시

```sparql
# 인물이 참여한 이벤트
SELECT ?event ?eventLabel ?date ?locationLabel
WHERE {
  wd:Q868 wdt:P1344 ?event .  # Q868 = Aristotle, P1344 = participant in

  OPTIONAL { ?event wdt:P585 ?date . }  # point in time
  OPTIONAL { ?event wdt:P276 ?location . }  # location

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
```

### 인물-이벤트 관계 (P1344, P793)

| Property | 의미 | 예시 |
|----------|------|------|
| P1344 | participant in | 알렉산더 → 이수스 전투 |
| P793 | significant event | 소크라테스 → 소크라테스 재판 |
| P1923 | participating team | (팀 스포츠용) |

---

## 12. 전체 파이프라인

```
Phase 1: 인물 수집
┌─────────────────────────────────────────────────────┐
│ Wikidata → 역사적 인물 (카테고리별)                  │
│   - philosophers, rulers, military, artists...      │
│   - 약 50,000명 예상                                 │
└─────────────────────────────────────────────────────┘
                    ↓
Phase 2: DB 매칭 & 통합
┌─────────────────────────────────────────────────────┐
│ Wikidata 인물 vs 기존 DB                            │
│   - 매칭됨 → wikidata_id 연결, data_quality=verified │
│   - 미매칭 → 새로 추가 또는 별도 관리                │
│   - 중복 → canonical_id로 통합                      │
└─────────────────────────────────────────────────────┘
                    ↓
Phase 3: 소스 수집
┌─────────────────────────────────────────────────────┐
│ 각 인물의 Wikipedia 문서 가져오기                    │
│   - sitelinks에서 URL 추출                          │
│   - sources 테이블에 저장                           │
│   - person_sources 연결                             │
└─────────────────────────────────────────────────────┘
                    ↓
Phase 4: 이벤트 수집
┌─────────────────────────────────────────────────────┐
│ 인물 관련 이벤트 가져오기                            │
│   - P1344 (participant in)                          │
│   - P793 (significant event)                        │
│   - events 테이블에 저장                            │
│   - person_events 연결                              │
└─────────────────────────────────────────────────────┘
                    ↓
Phase 5: 이벤트 소스 수집
┌─────────────────────────────────────────────────────┐
│ 이벤트의 Wikipedia 문서 가져오기                     │
│   - event_sources 연결                              │
└─────────────────────────────────────────────────────┘
                    ↓
Phase 6: 노이즈 정리
┌─────────────────────────────────────────────────────┐
│ 기존 DB의 노이즈 데이터 처리                         │
│   - data_quality = 'noise' 마킹                     │
│   - API에서 제외 (이미 적용됨)                       │
│   - 선택적으로 삭제                                 │
└─────────────────────────────────────────────────────┘
```

---

## 13. 기존 데이터 품질 업데이트

### 자동 품질 분류 로직

```python
def classify_person_quality(person):
    # 1. Wikidata 검증됨
    if person.wikidata_id:
        return 'verified'

    # 2. 노이즈 패턴
    noise_patterns = ['Mrs.', 'Miss ', 'Mr. ', 'Sig.']
    if any(person.name.startswith(p) for p in noise_patterns):
        return 'noise'

    # 3. 생몰년 있고 mention_count > 5
    if (person.birth_year or person.death_year) and person.mention_count > 5:
        return 'sourced'

    # 4. 기본값
    return 'extracted'
```

### 일괄 업데이트 스크립트

```bash
python poc/scripts/update_person_quality.py
# - noise: 18,531명
# - extracted: ~180,000명
# - sourced: ~60,000명
# - verified: 759명 (현재)
```

---

## 14. 다음 단계 (우선순위)

### 즉시 실행
- [x] fetch_wikidata_persons.py 스크립트 작성
- [x] 철학자 카테고리로 테스트 (500명)
- [ ] 매칭 스크립트 성능 최적화 (현재 느림)
- [ ] data_quality 컬럼 추가 마이그레이션

### 단기
- [ ] 전체 카테고리 확장 (rulers, military 등)
- [ ] Wikipedia sitelinks 가져오기 추가
- [ ] 이벤트 수집 스크립트 작성
- [ ] sources 테이블 연동

### 중기
- [ ] 기존 데이터 품질 분류 적용
- [ ] 중복 인물 통합 (canonical_id)
- [ ] UI에서 신뢰도 표시
- [ ] FactGrid 연동
