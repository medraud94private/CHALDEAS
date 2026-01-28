# 데이터 재구성 전체 기획

> 목표: 쓰레기 DB → 깨끗하고 완벽한 형태로

## 현재 상태

### DB
```
persons: 286,566개
├── QID 있음: 101,925개 (unique 91,596개) → 살림
└── QID 없음: 184,641개 → 분석 후 결정

locations: 40,613개 (좌표 없는 것 많음)
events: 46,704개 (연도 불명확한 것 많음)
```

### 책 추출 데이터
```
166권 추출 완료
├── persons/locations/events 이름만 있음
└── chunk_results에 context 있음 → 역추적 가능
```

---

## Phase 1: DB 정리 - QID 있는 것

### Step 1.1: QID 중복 합치기

**문제**: 같은 QID에 여러 레코드
```sql
-- 예시: Napoleon (Q517)이 여러 개
SELECT wikidata_id, COUNT(*), array_agg(name)
FROM persons
WHERE wikidata_id IS NOT NULL
GROUP BY wikidata_id
HAVING COUNT(*) > 1;
```

**해결**:
```python
def merge_by_qid():
    """같은 QID를 가진 레코드들 합치기"""

    # 1. 중복 QID 찾기
    duplicates = db.query("""
        SELECT wikidata_id, array_agg(id) as ids
        FROM persons
        WHERE wikidata_id IS NOT NULL
        GROUP BY wikidata_id
        HAVING COUNT(*) > 1
    """)

    for dup in duplicates:
        qid = dup.wikidata_id
        ids = dup.ids

        # 2. primary 선택 (가장 정보 많은 것)
        primary = select_best_record(ids)
        others = [id for id in ids if id != primary.id]

        # 3. 다른 이름들은 alias로 저장
        for other_id in others:
            other = get_person(other_id)
            save_alias(
                entity_type='person',
                entity_id=primary.id,
                alias=other.name,
                alias_type='merged'
            )

        # 4. 관계 데이터 이전
        migrate_relationships(from_ids=others, to_id=primary.id)

        # 5. 중복 레코드 삭제
        delete_persons(others)
```

**결과**: 91,596개 unique persons (QID 기반)

### Step 1.2: Wikidata에서 정보 보강

**부족한 정보**:
- birth_year, death_year 없는 것
- description 없는 것
- 한국어 이름 없는 것

**해결**:
```python
def enrich_from_wikidata():
    """Wikidata에서 기본 정보 가져오기"""

    persons = db.query("""
        SELECT id, wikidata_id
        FROM persons
        WHERE wikidata_id IS NOT NULL
        AND (birth_year IS NULL OR description IS NULL)
    """)

    for p in persons:
        info = fetch_wikidata(p.wikidata_id)

        db.update(p.id, {
            'birth_year': info.birth_year,
            'death_year': info.death_year,
            'description': info.description,
            'name_ko': info.name_ko,
            'image_url': info.image_url,
            'wikipedia_url': info.wikipedia_url
        })
```

---

## Phase 2: DB 정리 - QID 없는 것

### Step 2.1: 출처 분석

**184,641개 QID 없는 것들 어디서 왔나?**

```python
def analyze_no_qid_sources():
    """QID 없는 엔티티들의 출처 분석"""

    # text_mentions나 다른 메타데이터에서 출처 확인
    results = db.query("""
        SELECT p.id, p.name, tm.source_id, s.title as source_name
        FROM persons p
        LEFT JOIN text_mentions tm ON p.id = tm.entity_id
        LEFT JOIN sources s ON tm.source_id = s.id
        WHERE p.wikidata_id IS NULL
    """)

    # 출처별 그룹화
    by_source = group_by(results, 'source_name')

    for source, entities in by_source.items():
        print(f"{source}: {len(entities)}개")
```

**예상 결과**:
```
britannica_1911: 50,000개 → 품질 좋음, 살림
dbpedia: 30,000개 → 품질 중간
gutenberg NER: 80,000개 → 품질 낮음, 검토 필요
unknown: 20,000개 → 버림
```

### Step 2.2: 품질별 처리

**A. 품질 좋은 출처 (britannica 등)**:
```python
def process_good_sources():
    """품질 좋은 출처의 엔티티 처리"""

    good_sources = ['britannica_1911', 'stanford_encyclopedia']

    for entity in get_entities_from_sources(good_sources):
        # Wikidata 검색 시도
        qid = search_wikidata(
            name=entity.name,
            context=entity.description,
            birth_year=entity.birth_year
        )

        if qid:
            # QID 찾음 → 기존 것과 합치거나 업데이트
            existing = get_by_qid(qid)
            if existing:
                merge_entities(existing, entity)
            else:
                entity.wikidata_id = qid
                entity.verification_status = 'verified'
        else:
            # QID 못 찾음 → unverified로 유지, context 저장
            entity.verification_status = 'unverified'
            entity.confidence_score = 0.7  # 출처 좋으니까 중간 신뢰도
```

**B. 품질 낮은 출처**:
```python
def process_low_quality():
    """품질 낮은 출처 처리"""

    for entity in get_low_quality_entities():
        # context 충분한가?
        if has_sufficient_context(entity):
            # Wikidata 검색
            qid = search_wikidata(entity.name, entity.context)
            if qid:
                merge_or_update(entity, qid)
            else:
                entity.verification_status = 'unverified'
                entity.confidence_score = 0.3
        else:
            # context 없으면 삭제 후보
            entity.verification_status = 'pending_deletion'
```

### Step 2.3: Richard 문제 해결

**현재 상태**: "Richard" 이름 가진 것들이 섞여 있음

```python
def resolve_richard_problem():
    """같은 이름, 다른 사람 분리"""

    # Richard로 시작하는 모든 엔티티
    richards = db.query("""
        SELECT * FROM persons
        WHERE name ILIKE 'richard%'
        AND wikidata_id IS NULL
    """)

    for richard in richards:
        # context에서 단서 찾기
        context = get_context(richard)  # text_mentions에서

        # Wikidata 검색
        candidates = search_wikidata_candidates(
            name=richard.name,
            context=context,
            limit=10
        )

        if len(candidates) == 1 and candidates[0].confidence > 0.9:
            # 확실한 매칭
            richard.wikidata_id = candidates[0].qid
            richard.verification_status = 'verified'
        elif len(candidates) > 1:
            # 여러 후보 → 수동 검토 큐
            add_to_review_queue(richard, candidates)
        else:
            # 후보 없음 → unverified
            richard.verification_status = 'unverified'
```

**수동 검토 큐**:
```
Richard 검토 필요:
1. "Richard" (ID: 12345)
   - context: "King of England, Crusade"
   - 후보: Richard I (Q190112), Richard II (Q130432)
   - 선택: [ ]

2. "Richard the Lionheart" (ID: 12346)
   - context: "led Third Crusade"
   - 후보: Richard I (Q190112)
   - 자동 매칭 가능 (confidence 0.95)
```

---

## Phase 3: 책 추출 데이터 정리

### Step 3.1: Context 역추적

```python
def extract_context_from_chunks():
    """chunk_results에서 context 추출"""

    for book_file in get_extraction_files():
        data = load_json(book_file)
        book_id = data['book_id']

        # 엔티티별 context 매핑
        entity_contexts = {}

        for chunk in data['chunk_results']:
            text = chunk['text_preview']

            for person in chunk.get('persons', []):
                if person not in entity_contexts:
                    entity_contexts[person] = []

                # context = 해당 청크의 텍스트
                entity_contexts[person].append({
                    'text': text,
                    'chunk_id': chunk['chunk_id'],
                    'book_id': book_id
                })

        # 저장
        save_entity_contexts(book_id, entity_contexts)
```

**결과 예시**:
```json
{
  "Hrothgar": {
    "contexts": [
      "Beowulf bode in the burg of the Scyldings... Hrothgar...",
      "King Hrothgar built the great hall..."
    ],
    "book": "Beowulf",
    "mentions": 15
  }
}
```

### Step 3.2: DB 매칭

```python
def match_book_entities():
    """책에서 추출한 엔티티를 DB와 매칭"""

    for book_id, entities in get_book_entities():
        for entity_name, info in entities.items():
            context = combine_contexts(info['contexts'])

            # 1. DB에서 정확한 이름 검색
            exact = db.query("""
                SELECT * FROM persons WHERE name = %s
            """, entity_name)

            if exact and exact.wikidata_id:
                # 정확한 매칭 + QID 있음 → 연결
                create_text_mention(exact.id, book_id, info)
                continue

            # 2. Wikidata 검색
            qid = search_wikidata(entity_name, context)

            if qid:
                # QID 찾음 → DB에서 찾거나 생성
                db_entity = get_or_create_by_qid(qid)
                create_text_mention(db_entity.id, book_id, info)
            else:
                # QID 없음 → unverified로 생성
                db_entity = create_unverified_entity(
                    name=entity_name,
                    context=context,
                    source=book_id
                )
                create_text_mention(db_entity.id, book_id, info)
```

---

## Phase 4: 새 파이프라인 구축

### Step 4.1: 개선된 추출 프롬프트

```python
EXTRACTION_PROMPT = """
Extract historical entities from this text.

IMPORTANT:
1. Use FULL names with titles/epithets
   - "Richard I of England" not "Richard"
   - "Napoleon Bonaparte" not "Napoleon"

2. Include distinguishing context
   - Role, time period, key events
   - "King who led Third Crusade"

3. Output format:
{
  "persons": [
    {
      "name": "Richard I of England",
      "aliases": ["Richard the Lionheart", "Coeur de Lion"],
      "context": "King of England, led Third Crusade against Saladin",
      "time_hint": "1157-1199"
    }
  ],
  "locations": [...],
  "events": [...]
}

TEXT:
{text}
"""
```

### Step 4.2: 새 매칭 파이프라인

```python
def match_entity_v2(extracted: dict) -> MatchResult:
    """개선된 매칭 파이프라인"""

    name = extracted['name']
    aliases = extracted.get('aliases', [])
    context = extracted['context']
    time_hint = extracted.get('time_hint')

    # 1. QID로 DB 검색 (alias 테이블 포함)
    for search_name in [name] + aliases:
        db_match = db.query("""
            SELECT p.* FROM persons p
            LEFT JOIN entity_aliases ea ON p.id = ea.entity_id
            WHERE p.name ILIKE %s OR ea.alias ILIKE %s
        """, search_name, search_name)

        if db_match and db_match.wikidata_id:
            return MatchResult(
                matched=True,
                entity_id=db_match.id,
                method='db_exact',
                confidence=1.0
            )

    # 2. Wikidata 검색
    wikidata_results = search_wikidata(
        name=name,
        context=context,
        time_hint=time_hint,
        limit=5
    )

    if wikidata_results:
        best = select_best_match(wikidata_results, context)

        if best.confidence > 0.9:
            # 확실한 매칭
            db_entity = get_or_create_by_qid(best.qid)

            # alias 저장
            for alias in aliases:
                save_alias(db_entity.id, alias, 'book_extraction')

            return MatchResult(
                matched=True,
                entity_id=db_entity.id,
                qid=best.qid,
                method='wikidata',
                confidence=best.confidence
            )

    # 3. 매칭 실패 → unverified로 생성
    new_entity = create_entity(
        name=name,
        context=context,
        verification_status='unverified',
        confidence_score=0.5
    )

    for alias in aliases:
        save_alias(new_entity.id, alias, 'book_extraction')

    return MatchResult(
        matched=False,
        entity_id=new_entity.id,
        method='new_unverified',
        confidence=0.5
    )
```

---

## Phase 5: 검증 및 품질 관리

### Step 5.1: 신뢰도 시스템

```sql
-- persons 테이블에 추가
ALTER TABLE persons ADD COLUMN verification_status VARCHAR(20)
    DEFAULT 'unverified'
    CHECK (verification_status IN ('verified', 'unverified', 'manual', 'pending_deletion'));

ALTER TABLE persons ADD COLUMN confidence_score FLOAT DEFAULT 0.5;
ALTER TABLE persons ADD COLUMN source_count INTEGER DEFAULT 0;
```

**신뢰도 계산**:
```python
def calculate_confidence(entity_id):
    """엔티티 신뢰도 계산"""

    entity = get_entity(entity_id)
    score = 0.0

    # 1. QID 있으면 +0.4
    if entity.wikidata_id:
        score += 0.4

    # 2. 출처 개수 (최대 +0.3)
    source_count = count_text_mentions(entity_id)
    score += min(source_count * 0.1, 0.3)

    # 3. 출처 품질 (최대 +0.2)
    source_quality = get_source_quality_avg(entity_id)
    score += source_quality * 0.2

    # 4. 정보 완성도 (최대 +0.1)
    completeness = calculate_completeness(entity)
    score += completeness * 0.1

    return min(score, 1.0)
```

### Step 5.2: 수동 검토 시스템

```python
# 검토 필요한 엔티티 큐
review_queue = db.query("""
    SELECT * FROM persons
    WHERE verification_status = 'unverified'
    AND confidence_score < 0.7
    ORDER BY source_count DESC  -- 많이 언급된 것 먼저
    LIMIT 100
""")

# 검토 UI에서:
# 1. 엔티티 정보 표시
# 2. Wikidata 후보 표시
# 3. 관리자가 선택하거나 "해당 없음" 표시
```

---

## 실행 순서

### Week 1: Phase 1 (DB 정리 - QID 있는 것)
```
Day 1: QID 중복 분석
Day 2-3: merge_by_qid() 구현 및 실행
Day 4-5: Wikidata 정보 보강
Day 6-7: 검증 및 테스트
```

### Week 2: Phase 2 (DB 정리 - QID 없는 것)
```
Day 1: 출처 분석
Day 2-3: 품질별 분류
Day 4-5: Richard 문제 해결 (자동)
Day 6-7: 수동 검토 필요한 것 큐에 추가
```

### Week 3: Phase 3 (책 추출 데이터)
```
Day 1-2: context 역추적
Day 3-4: DB 매칭
Day 5-7: text_mentions 생성
```

### Week 4: Phase 4-5 (새 파이프라인 + 품질 관리)
```
Day 1-2: 새 추출 프롬프트
Day 3-4: 새 매칭 파이프라인
Day 5-7: 신뢰도 시스템 + 검토 UI
```

---

## 최종 결과

### DB 상태 (목표)
```
persons:
├── verified (QID 있음): ~100,000개
├── unverified (context로 식별): ~50,000개
├── pending_review: ~10,000개
└── 삭제됨: ~130,000개 (쓰레기)

모든 엔티티:
├── unique 식별 (QID 또는 context)
├── 중복 없음
├── 출처 추적 가능 (text_mentions)
└── 신뢰도 점수 있음
```

### 파이프라인
```
새 책 추출 → context 포함 → Wikidata 검색 →
QID 확정 or unverified → DB 연결 → text_mention 기록
```

### Richard 문제 해결됨
```
Before:
  - "Richard" (QID 없음, 누군지 모름)

After:
  - "Richard I of England" (Q190112) - verified
  - "Richard II of England" (Q130432) - verified
  - "Richard Nixon" (Q9588) - verified
  - "King Richard from [책]" - unverified, context로 식별
```
