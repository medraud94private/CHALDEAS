# Legacy System Analysis: 어떻게 DB가 쓰레기가 되었나

## 요약

**현재 DB 상태**:
- persons: 286,566개
- QID 있음: 101,925 (35%)
- QID 없음: 184,641 (65%) ← 쓰레기
- 중복: 수천 개 (같은 QID에 여러 레코드, 같은 인물이 다른 이름으로)

**근본 원인**:
- Wikidata QID를 Primary Key로 쓰지 않음
- 이름 기반 매칭/중복 체크
- 여러 소스에서 검증 없이 데이터 추가

---

## Phase 1: 원본 데이터 수집

### 스크립트
- `data/scripts/collect_all.py`
- 각 소스별 크롤러

### 소스 목록 (data/raw/)
```
arthurian/          - 아서왕 전설
atlas_academy/      - FGO 게임 데이터
augustana/          - 고전 텍스트
avalon/             - 역사 문서
britannica_1911/    - 1911년판 브리태니커
british_library/    - 영국 도서관
ctext/              - 중국 고전
dbpedia/            - DBpedia 덤프
fordham/            - 중세 자료
gamepress/          - FGO 위키
gutenberg/          - 구텐베르크
latin_library/      - 라틴어 텍스트
open_library/       - Open Library
...
```

### 문제점
- **소스마다 다른 포맷**: JSON, HTML, TXT 등
- **중복 데이터**: 같은 인물이 여러 소스에
- **품질 편차**: britannica_1911은 양호, 나머지는 불명확

---

## Phase 2: NER 추출 (Archivist)

### 스크립트
```
poc/scripts/archivist_fullscale.py
poc/scripts/archivist_fullscale_v2.py
poc/scripts/archivist_fullscale_v3.py
poc/scripts/archivist_phase2_*.py
```

### 로직
```python
# HybridNERPipeline 사용
# 1. spaCy로 1차 추출
# 2. LLM으로 2차 검증/보강

for file in data/raw/**/*.json:
    text = extract_text(file)
    entities = ner_pipeline.extract(text)
    save_to_results(entities)
```

### 출력
```
poc/data/archivist_results/
  britannica_1911/
    persons.json
    locations.json
    events.json
  gutenberg/
    persons.json
    ...
```

### 문제점
1. **이름만 추출**: "Richard", "Napoleon" (context 없음)
2. **중복 처리 안 함**: 같은 파일에서 "Napoleon"이 10번 나오면 10개 엔티티
3. **소스 간 중복**: britannica와 gutenberg에서 각각 "Napoleon" 추출 → 별개 취급

---

## Phase 3: Aggregation

### 스크립트
```
poc/scripts/aggregate_ner_results.py
```

### 로직
```python
# 모든 소스의 결과를 합침
all_persons = []
for source in sources:
    persons = load_json(f'{source}/persons.json')
    all_persons.extend(persons)

# "이름"으로 그룹화
grouped = group_by_name(all_persons)

# mention_count 계산
for name, entities in grouped.items():
    merged = {
        "name": name,
        "mention_count": len(entities),
        "sources": list(set(e["source"] for e in entities))
    }
    aggregated.append(merged)
```

### 출력
```
poc/data/integrated_ner_full/aggregated/
  persons.json      # 합쳐진 인물
  locations.json
  events.json
```

### 문제점
1. **이름 기반 그룹화**: "Richard" = 모든 Richard (Richard I, II, III, Nixon...)
2. **동명이인 구분 안 됨**: "John"이 1000번 나오면 mention_count=1000인 하나의 엔티티
3. **QID 없음**: 여전히 Wikidata 연결 안 됨

---

## Phase 4: DB Import

### 스크립트
```
poc/scripts/import_entities_to_db.py
poc/scripts/import_to_v1_db.py
```

### 로직
```python
# aggregated 결과를 DB에 삽입
persons = load_json('aggregated/persons.json')

for p in persons:
    # mention_count 필터
    if p['mention_count'] < MIN_MENTIONS:
        continue

    # 이름으로 중복 체크 (!!!)
    existing = db.query(Person).filter_by(name=p['name']).first()
    if existing:
        # 기존 것에 mention_count만 업데이트
        existing.mention_count += p['mention_count']
    else:
        # 새로 생성 (QID 없이!)
        db.add(Person(name=p['name'], ...))
```

### 문제점
1. **QID 없이 삽입**: wikidata_id = NULL
2. **이름 기반 중복 체크**: "Napoleon" 하나만 있으면 OK
3. **동명이인 전부 합쳐짐**: DB에 "Richard" 하나 → 모든 Richard가 이 레코드

---

## Phase 5: Wikidata Enrichment (재앙의 시작)

### 스크립트
```
poc/scripts/fetch_wikidata_persons.py
poc/scripts/fetch_wikidata_sources.py
poc/scripts/apply_wikidata_matches.py
poc/scripts/wikidata_match_persons.py
poc/scripts/wikidata_reconcile.py
```

### 의도
```
DB에 있는 인물들에 Wikidata QID를 연결하자
```

### 실제 로직 (문제)
```python
# Wikidata에서 인물 목록 가져옴
wikidata_persons = fetch_from_wikidata(category="rulers", limit=10000)

for wp in wikidata_persons:
    # DB에서 이름으로 검색 (!!!)
    db_person = db.query(Person).filter(
        Person.name.ilike(f"%{wp.name}%")
    ).first()

    if db_person:
        # 매칭됨 → QID 업데이트
        db_person.wikidata_id = wp.qid
    else:
        # 없음 → 새로 생성!!!
        db.add(Person(
            name=wp.name,
            wikidata_id=wp.qid,
            ...
        ))
```

### 문제점
1. **이름 매칭 실패**: "Napoleon Bonaparte" vs "Napoleon" → 매칭 안 됨
2. **새 레코드 생성**: 매칭 안 되면 새로 추가 → 중복
3. **결과**: "Napoleon" (QID 없음) + "Napoleon Bonaparte" (Q517) 둘 다 존재

---

## Phase 6: Wikipedia Import (재앙 심화)

### 스크립트
```
poc/scripts/kiwix_extract_persons.py
poc/scripts/kiwix_db_matcher.py
poc/scripts/import_wikipedia_to_db.py
poc/scripts/link_wikipedia_to_db.py
```

### 로직
```python
# Wikipedia ZIM에서 역사적 인물 추출
zim = Archive("wikipedia_en_nopic.zim")

for entry in zim:
    if is_historical_person(entry):
        person = extract_person_info(entry)

        # DB에서 검색 (이름 + fuzzy)
        match = find_in_db(person.name)

        if match:
            # 연결
            update_with_wikipedia_info(match, person)
        else:
            # 새로 추가!!! (또 중복)
            db.add(Person(...))
```

### 문제점
1. **Wikipedia 전체 덤프**: 수백만 인물 시도
2. **매칭 실패 → 새 레코드**: "Richard I of England" vs "Richard" 매칭 안 됨
3. **결과**: 같은 인물이 3-4개 레코드로 존재

---

## Phase 7: 관계 생성 (카오스)

### 스크립트
```
poc/scripts/create_relationships_from_links.py
poc/scripts/create_relationships_from_mentions.py
poc/scripts/create_missing_relationships.py
poc/scripts/build_event_chains.py
```

### 문제점
- 중복된 엔티티들 사이에 관계 생성
- "Napoleon" (ID: 100) ↔ "Napoleon Bonaparte" (ID: 200) 별개 취급
- 관계도 중복

---

## Phase 8: 책 추출 시도 (현재)

### 스크립트
```
tools/book_extractor/server.py
tools/book_extractor/entity_matcher.py
```

### 문제점 (이미 논의됨)
1. 이름만 추출
2. context 없음
3. 쓰레기 DB에 매칭 시도 → 의미 없음

---

## 스크립트 목록 (110개)

### 카테고리별 분류

**NER 추출 (15개)**
```
archivist_fullscale.py
archivist_fullscale_v2.py
archivist_fullscale_v3.py
archivist_phase2_batch.py
archivist_phase2_parallel.py
archivist_phase2_v2.py
archivist_phase2_v3.py
archivist_phase2_v4.py
archivist_review_pending.py
aggregate_ner_results.py
analyze_data_quality.py
analyze_entity_tiers.py
analyze_extractions.py
...
```

**DB Import (10개)**
```
import_entities_to_db.py
import_to_v1_db.py
import_sources_and_mentions.py
import_wikipedia_to_db.py
import_enriched_to_sources.py
import_book_extractions.py
...
```

**Wikidata (10개)**
```
fetch_wikidata_persons.py
fetch_wikidata_sources.py
apply_wikidata_matches.py
wikidata_match_persons.py
wikidata_match_parallel.py
wikidata_reconcile.py
wikidata_resume.py
wikidata_continue.py
apply_reverse_wikidata.py
...
```

**Wikipedia/Kiwix (10개)**
```
kiwix_db_matcher.py
kiwix_extract_all.py
kiwix_extract_full.py
kiwix_extract_parallel.py
kiwix_extract_persons.py
kiwix_reader.py
kiwix_reconcile.py
kiwix_rescan_events.py
link_wikipedia_to_db.py
...
```

**Enrichment (15개)**
```
enrich_event_descriptions.py
enrich_events_llm.py
enrich_locations.py
enrich_locations_pleiades.py
enrich_persons_llm.py
enrich_wikipedia_extract.py
apply_enrichment.py
apply_locations_enrichment.py
apply_persons_enrichment.py
...
```

**Relationship (10개)**
```
create_relationships_from_links.py
create_relationships_from_mentions.py
create_relationships_from_mentions_v2.py
create_event_event_relationships.py
create_missing_relationships.py
build_event_chains.py
classify_connections.py
link_persons_events_via_source.py
link_persons_locations_via_source.py
link_persons_persons_via_source.py
...
```

**기타 (40개+)**
```
benchmark_local_models.py
build_gazetteer.py
check_false_positives.py
cleanup_false_positives.py
compare_enrichment_models.py
dashboard_server.py
deduplicate_events.py
download_gutenberg_books.py
generate_person_story.py
normalize_entities.py
normalize_entities_v2.py
test_*.py
update_*.py
...
```

---

## 근본 설계 실수

### 1. Primary Key 문제
```
잘못된 설계: name이 사실상 PK
올바른 설계: wikidata_id가 PK (UNIQUE, NOT NULL)
```

### 2. 데이터 흐름 문제
```
잘못된 흐름:
  원본 → NER 추출 → DB 삽입 → Wikidata 매칭 시도

올바른 흐름:
  원본 → NER 추출 → Wikidata 검색 → QID 확정 → DB 삽입
```

### 3. 중복 처리 문제
```
잘못된 처리: 이름 비교 → 같으면 합침
올바른 처리: QID 비교 → 같으면 합침
```

### 4. 검증 부재
```
잘못: 추출 → 바로 DB
올바: 추출 → Wikidata 검증 → 확인된 것만 DB
```

---

## 결론

**110개 스크립트**를 만들면서 **같은 실수를 반복**:
1. 이름 기반 매칭
2. 검증 없이 DB 삽입
3. 중복 생성

**결과**: 286,566개 중 65%가 쓰레기 (QID 없음, 중복)

**해결책**: CLEAN_START_PLAN.md 참조
- Wikidata QID를 Primary Key로
- 추출 시 Wikidata 먼저 검색
- QID 없으면 DB에 안 넣음
