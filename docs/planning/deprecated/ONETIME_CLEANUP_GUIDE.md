# 일회성 정리 작업 가이드

> 각 단계별 상세 방법 + 테스트

---

## 1. QID 중복 합치기

### 목표
같은 Wikidata QID를 가진 여러 레코드를 하나로 합침

### Before
```
ID: 419   | name: "Napoleon III"        | wikidata_id: Q7721
ID: 149046| name: "LOUIS NAPOLEON..."   | wikidata_id: Q7721
ID: 244157| name: "Emperor Napoleon III"| wikidata_id: Q7721
```

### After
```
ID: 419   | name: "Napoleon III"        | wikidata_id: Q7721

entity_aliases:
  - "LOUIS NAPOLEON BONAPARTE" → 419
  - "Emperor Napoleon III" → 419
```

### 실행 방법

```python
# poc/scripts/cleanup/merge_qid_duplicates.py

import psycopg2
from psycopg2.extras import RealDictCursor

def merge_qid_duplicates():
    conn = psycopg2.connect(
        host='localhost', port=5432, dbname='chaldeas',
        user='chaldeas', password='chaldeas_dev'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. 중복 QID 찾기
    cur.execute("""
        SELECT wikidata_id, array_agg(id ORDER BY id) as ids, array_agg(name ORDER BY id) as names
        FROM persons
        WHERE wikidata_id IS NOT NULL
        GROUP BY wikidata_id
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    print(f"중복 QID 개수: {len(duplicates)}")

    merged_count = 0
    for dup in duplicates:
        qid = dup['wikidata_id']
        ids = dup['ids']
        names = dup['names']

        # 2. primary 선택 (첫 번째 = 가장 오래된 것)
        primary_id = ids[0]
        primary_name = names[0]
        other_ids = ids[1:]
        other_names = names[1:]

        print(f"\n{qid}: {names}")
        print(f"  Primary: [{primary_id}] {primary_name}")
        print(f"  Merge: {list(zip(other_ids, other_names))}")

        # 3. 다른 이름들 alias로 저장
        for other_id, other_name in zip(other_ids, other_names):
            if other_name != primary_name:
                cur.execute("""
                    INSERT INTO entity_aliases (entity_type, entity_id, alias, alias_type)
                    VALUES ('person', %s, %s, 'merged')
                    ON CONFLICT (entity_type, entity_id, alias) DO NOTHING
                """, (primary_id, other_name))

        # 4. 관계 데이터 이전
        for other_id in other_ids:
            # person_events
            cur.execute("""
                UPDATE person_events SET person_id = %s WHERE person_id = %s
            """, (primary_id, other_id))

            # person_locations
            cur.execute("""
                UPDATE person_locations SET person_id = %s WHERE person_id = %s
            """, (primary_id, other_id))

            # person_relationships
            cur.execute("""
                UPDATE person_relationships SET person_id = %s WHERE person_id = %s
            """, (primary_id, other_id))
            cur.execute("""
                UPDATE person_relationships SET related_person_id = %s WHERE related_person_id = %s
            """, (primary_id, other_id))

            # text_mentions
            cur.execute("""
                UPDATE text_mentions SET entity_id = %s
                WHERE entity_type = 'person' AND entity_id = %s
            """, (primary_id, other_id))

        # 5. 중복 레코드 삭제
        cur.execute("""
            DELETE FROM persons WHERE id = ANY(%s)
        """, (other_ids,))

        merged_count += len(other_ids)

    conn.commit()
    print(f"\n총 {merged_count}개 레코드 합침")
    conn.close()

if __name__ == "__main__":
    merge_qid_duplicates()
```

### 테스트

```python
# poc/scripts/cleanup/test_merge_qid.py

def test_merge_qid():
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 테스트 1: 중복 QID 없어야 함
    cur.execute("""
        SELECT wikidata_id, COUNT(*)
        FROM persons
        WHERE wikidata_id IS NOT NULL
        GROUP BY wikidata_id
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    assert len(duplicates) == 0, f"중복 QID 남아있음: {len(duplicates)}개"
    print("✅ 테스트 1 통과: 중복 QID 없음")

    # 테스트 2: Napoleon III (Q7721) 확인
    cur.execute("""
        SELECT * FROM persons WHERE wikidata_id = 'Q7721'
    """)
    results = cur.fetchall()
    assert len(results) == 1, f"Q7721이 {len(results)}개 있음"
    print(f"✅ 테스트 2 통과: Q7721 = {results[0]['name']}")

    # 테스트 3: alias 저장됐나
    cur.execute("""
        SELECT * FROM entity_aliases
        WHERE entity_type = 'person'
        AND alias_type = 'merged'
        LIMIT 10
    """)
    aliases = cur.fetchall()
    print(f"✅ 테스트 3: merged alias {len(aliases)}개 저장됨")
    for a in aliases[:5]:
        print(f"   - {a['alias']} → entity {a['entity_id']}")

    conn.close()
    print("\n모든 테스트 통과!")

if __name__ == "__main__":
    test_merge_qid()
```

### 실행 순서
```bash
# 1. 백업
pg_dump -U chaldeas chaldeas > backup_before_merge.sql

# 2. 실행
python poc/scripts/cleanup/merge_qid_duplicates.py

# 3. 테스트
python poc/scripts/cleanup/test_merge_qid.py

# 4. 문제 있으면 롤백
psql -U chaldeas chaldeas < backup_before_merge.sql
```

---

## 2. QID 없는 것 분석

### 목표
184,641개 QID 없는 엔티티가 어디서 왔는지 파악

### 실행 방법

```python
# poc/scripts/cleanup/analyze_no_qid.py

def analyze_no_qid():
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=== QID 없는 persons 분석 ===\n")

    # 1. 총 개수
    cur.execute("SELECT COUNT(*) FROM persons WHERE wikidata_id IS NULL")
    total = cur.fetchone()['count']
    print(f"총 개수: {total:,}")

    # 2. 이름 패턴 분석
    print("\n--- 이름 패턴 ---")
    cur.execute("""
        SELECT
            CASE
                WHEN name ~ '^[A-Z][a-z]+ [A-Z][a-z]+$' THEN 'First Last'
                WHEN name ~ '^[A-Z][a-z]+$' THEN 'Single Name'
                WHEN name ~ '^Dr\.' THEN 'Dr. prefix'
                WHEN name ~ '^[A-Z]+$' THEN 'ALL CAPS'
                WHEN name ~ '[0-9]' THEN 'Contains numbers'
                ELSE 'Other'
            END as pattern,
            COUNT(*) as cnt
        FROM persons
        WHERE wikidata_id IS NULL
        GROUP BY pattern
        ORDER BY cnt DESC
    """)
    for row in cur.fetchall():
        print(f"  {row['pattern']}: {row['cnt']:,}")

    # 3. 샘플 출력
    print("\n--- 샘플 (QID 없는 것) ---")
    cur.execute("""
        SELECT id, name FROM persons
        WHERE wikidata_id IS NULL
        ORDER BY RANDOM()
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(f"  [{row['id']}] {row['name']}")

    # 4. 출처 분석 (text_mentions에서)
    print("\n--- 출처별 분포 ---")
    cur.execute("""
        SELECT s.title, COUNT(DISTINCT p.id) as person_count
        FROM persons p
        LEFT JOIN text_mentions tm ON p.id = tm.entity_id AND tm.entity_type = 'person'
        LEFT JOIN sources s ON tm.source_id = s.id
        WHERE p.wikidata_id IS NULL
        GROUP BY s.title
        ORDER BY person_count DESC
        LIMIT 20
    """)
    for row in cur.fetchall():
        source = row['title'] or '(출처 없음)'
        print(f"  {source}: {row['person_count']:,}")

    conn.close()

if __name__ == "__main__":
    analyze_no_qid()
```

### 테스트 (분석 결과 확인)

```python
# 분석 결과를 보고 판단:
# - "First Last" 패턴 → 실제 인물일 가능성 높음
# - "ALL CAPS" → OCR 오류일 수 있음
# - "Contains numbers" → 버그 데이터
# - "(출처 없음)" → 쓰레기

# 결과 파일로 저장
python poc/scripts/cleanup/analyze_no_qid.py > analysis_no_qid.txt
```

---

## 3. 쓰레기 데이터 삭제

### 목표
품질 낮은 데이터 삭제

### 삭제 기준
```
1. 이름에 숫자 포함 (예: "Richard 0. MoOORMICK")
2. 이름이 너무 짧음 (2글자 이하)
3. 이름이 너무 김 (100자 이상)
4. 출처 없고 QID 없음
5. "(likely not a person)" 같은 표시 있음
```

### 실행 방법

```python
# poc/scripts/cleanup/delete_garbage.py

def delete_garbage(dry_run=True):
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 삭제 대상 찾기
    cur.execute("""
        SELECT id, name FROM persons
        WHERE wikidata_id IS NULL
        AND (
            name ~ '[0-9]'                          -- 숫자 포함
            OR LENGTH(name) <= 2                    -- 너무 짧음
            OR LENGTH(name) >= 100                  -- 너무 김
            OR name ILIKE '%not a person%'          -- 명시적 표시
            OR name ILIKE '%unknown%'
            OR name ~ '^[^a-zA-Z]'                  -- 문자로 시작 안 함
        )
    """)
    garbage = cur.fetchall()

    print(f"삭제 대상: {len(garbage)}개")
    for g in garbage[:20]:
        print(f"  [{g['id']}] {g['name']}")

    if dry_run:
        print("\n(dry_run=True, 실제 삭제 안 함)")
        return

    # 실제 삭제
    ids = [g['id'] for g in garbage]

    # 관련 데이터 먼저 삭제
    cur.execute("DELETE FROM text_mentions WHERE entity_type = 'person' AND entity_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM entity_aliases WHERE entity_type = 'person' AND entity_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM person_events WHERE person_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM person_locations WHERE person_id = ANY(%s)", (ids,))
    cur.execute("DELETE FROM person_relationships WHERE person_id = ANY(%s) OR related_person_id = ANY(%s)", (ids, ids))

    # persons 삭제
    cur.execute("DELETE FROM persons WHERE id = ANY(%s)", (ids,))

    conn.commit()
    print(f"\n{len(ids)}개 삭제 완료")
    conn.close()

if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    delete_garbage(dry_run=dry_run)
```

### 테스트

```python
# poc/scripts/cleanup/test_delete_garbage.py

def test_delete_garbage():
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    # 테스트 1: 숫자 포함된 이름 없어야 함
    cur.execute("""
        SELECT COUNT(*) FROM persons
        WHERE wikidata_id IS NULL AND name ~ '[0-9]'
    """)
    count = cur.fetchone()[0]
    assert count == 0, f"숫자 포함된 이름 {count}개 남아있음"
    print("✅ 테스트 1 통과: 숫자 포함 이름 없음")

    # 테스트 2: 너무 짧은 이름 없어야 함
    cur.execute("""
        SELECT COUNT(*) FROM persons
        WHERE wikidata_id IS NULL AND LENGTH(name) <= 2
    """)
    count = cur.fetchone()[0]
    assert count == 0, f"짧은 이름 {count}개 남아있음"
    print("✅ 테스트 2 통과: 짧은 이름 없음")

    # 테스트 3: 정상 데이터는 남아있어야 함
    cur.execute("SELECT COUNT(*) FROM persons WHERE wikidata_id IS NOT NULL")
    count = cur.fetchone()[0]
    assert count > 80000, f"QID 있는 데이터가 너무 적음: {count}"
    print(f"✅ 테스트 3 통과: QID 있는 데이터 {count:,}개")

    conn.close()
    print("\n모든 테스트 통과!")
```

### 실행 순서
```bash
# 1. dry run (삭제 대상 확인)
python poc/scripts/cleanup/delete_garbage.py

# 2. 백업
pg_dump -U chaldeas chaldeas > backup_before_delete.sql

# 3. 실제 삭제
python poc/scripts/cleanup/delete_garbage.py --execute

# 4. 테스트
python poc/scripts/cleanup/test_delete_garbage.py
```

---

## 4. Wikidata 정보 보강

### 목표
QID 있는데 birth_year, description 없는 것 채우기

### 실행 방법

```python
# poc/scripts/cleanup/enrich_from_wikidata.py

import requests
import time

WIKIDATA_API = "https://www.wikidata.org/w/api.php"

def fetch_wikidata_info(qid):
    """Wikidata에서 정보 가져오기"""
    params = {
        'action': 'wbgetentities',
        'ids': qid,
        'format': 'json',
        'languages': 'en|ko',
        'props': 'labels|descriptions|claims'
    }

    resp = requests.get(WIKIDATA_API, params=params)
    data = resp.json()

    if 'entities' not in data or qid not in data['entities']:
        return None

    entity = data['entities'][qid]

    # 이름
    name_en = entity.get('labels', {}).get('en', {}).get('value')
    name_ko = entity.get('labels', {}).get('ko', {}).get('value')

    # 설명
    desc_en = entity.get('descriptions', {}).get('en', {}).get('value')
    desc_ko = entity.get('descriptions', {}).get('ko', {}).get('value')

    # 생년/몰년
    claims = entity.get('claims', {})
    birth_year = None
    death_year = None

    if 'P569' in claims:  # date of birth
        try:
            birth_str = claims['P569'][0]['mainsnak']['datavalue']['value']['time']
            birth_year = int(birth_str[1:5]) if birth_str[0] == '+' else -int(birth_str[1:5])
        except:
            pass

    if 'P570' in claims:  # date of death
        try:
            death_str = claims['P570'][0]['mainsnak']['datavalue']['value']['time']
            death_year = int(death_str[1:5]) if death_str[0] == '+' else -int(death_str[1:5])
        except:
            pass

    return {
        'name_en': name_en,
        'name_ko': name_ko,
        'description': desc_en,
        'description_ko': desc_ko,
        'birth_year': birth_year,
        'death_year': death_year
    }


def enrich_persons(limit=1000):
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 정보 부족한 것 찾기
    cur.execute("""
        SELECT id, wikidata_id, name
        FROM persons
        WHERE wikidata_id IS NOT NULL
        AND (birth_year IS NULL OR description IS NULL OR name_ko IS NULL)
        LIMIT %s
    """, (limit,))
    persons = cur.fetchall()

    print(f"보강 대상: {len(persons)}개")

    enriched = 0
    for i, p in enumerate(persons):
        if i % 100 == 0:
            print(f"진행: {i}/{len(persons)}")

        info = fetch_wikidata_info(p['wikidata_id'])
        if not info:
            continue

        # 업데이트
        cur.execute("""
            UPDATE persons SET
                birth_year = COALESCE(birth_year, %s),
                death_year = COALESCE(death_year, %s),
                description = COALESCE(description, %s),
                name_ko = COALESCE(name_ko, %s)
            WHERE id = %s
        """, (
            info['birth_year'],
            info['death_year'],
            info['description'],
            info['name_ko'],
            p['id']
        ))
        enriched += 1

        time.sleep(0.1)  # rate limit

    conn.commit()
    print(f"\n{enriched}개 보강 완료")
    conn.close()

if __name__ == "__main__":
    enrich_persons(limit=1000)  # 처음엔 1000개로 테스트
```

### 테스트

```python
# poc/scripts/cleanup/test_enrich.py

def test_enrich():
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    # 테스트 1: Napoleon (Q517) 정보 확인
    cur.execute("""
        SELECT name, name_ko, birth_year, death_year, description
        FROM persons WHERE wikidata_id = 'Q517'
    """)
    napoleon = cur.fetchone()
    print(f"Napoleon: {napoleon}")

    assert napoleon[2] == 1769, f"birth_year가 {napoleon[2]}"
    assert napoleon[3] == 1821, f"death_year가 {napoleon[3]}"
    assert napoleon[1] is not None, "name_ko 없음"
    print("✅ 테스트 1 통과: Napoleon 정보 정확")

    # 테스트 2: 보강된 비율
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE birth_year IS NOT NULL) as has_birth,
            COUNT(*) FILTER (WHERE description IS NOT NULL) as has_desc,
            COUNT(*) as total
        FROM persons
        WHERE wikidata_id IS NOT NULL
    """)
    stats = cur.fetchone()
    print(f"\n보강 현황:")
    print(f"  birth_year: {stats[0]:,} / {stats[2]:,} ({stats[0]*100//stats[2]}%)")
    print(f"  description: {stats[1]:,} / {stats[2]:,} ({stats[1]*100//stats[2]}%)")

    conn.close()
```

---

## 5. 166권 Context 역추적

### 목표
chunk_results에서 엔티티별 context 추출

### 실행 방법

```python
# poc/scripts/cleanup/extract_book_contexts.py

import json
from pathlib import Path

RESULTS_DIR = Path("poc/data/book_samples/extraction_results")
OUTPUT_DIR = Path("poc/data/book_contexts")
OUTPUT_DIR.mkdir(exist_ok=True)

def extract_contexts():
    extraction_files = list(RESULTS_DIR.glob("*_extraction.json"))
    print(f"처리할 책: {len(extraction_files)}권")

    for i, f in enumerate(extraction_files):
        if i % 20 == 0:
            print(f"진행: {i}/{len(extraction_files)}")

        data = json.load(open(f, 'r', encoding='utf-8'))
        book_id = data['book_id']
        title = data.get('title', book_id)

        # 엔티티별 context 수집
        entity_contexts = {
            'persons': {},
            'locations': {},
            'events': {}
        }

        for chunk in data.get('chunk_results', []):
            text = chunk.get('text_preview', '')
            chunk_id = chunk.get('chunk_id', 0)

            for entity_type in ['persons', 'locations', 'events']:
                for entity in chunk.get(entity_type, []):
                    if entity not in entity_contexts[entity_type]:
                        entity_contexts[entity_type][entity] = {
                            'name': entity,
                            'contexts': [],
                            'mention_count': 0
                        }

                    entity_contexts[entity_type][entity]['contexts'].append({
                        'text': text[:500],  # 500자로 제한
                        'chunk_id': chunk_id
                    })
                    entity_contexts[entity_type][entity]['mention_count'] += 1

        # 저장
        output = {
            'book_id': book_id,
            'title': title,
            'source_file': f.name,
            'entities': entity_contexts
        }

        output_file = OUTPUT_DIR / f"{book_id}_contexts.json"
        json.dump(output, open(output_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f"\n완료: {OUTPUT_DIR}")

if __name__ == "__main__":
    extract_contexts()
```

### 테스트

```python
# poc/scripts/cleanup/test_extract_contexts.py

def test_extract_contexts():
    import json
    from pathlib import Path

    OUTPUT_DIR = Path("poc/data/book_contexts")

    # 테스트 1: 파일 생성됐나
    context_files = list(OUTPUT_DIR.glob("*_contexts.json"))
    assert len(context_files) > 0, "context 파일 없음"
    print(f"✅ 테스트 1 통과: {len(context_files)}개 파일 생성")

    # 테스트 2: Beowulf context 확인
    beowulf = OUTPUT_DIR / "Beowulf_981_contexts.json"
    if beowulf.exists():
        data = json.load(open(beowulf))
        persons = data['entities']['persons']

        assert 'Hrothgar' in persons, "Hrothgar 없음"
        hrothgar = persons['Hrothgar']
        assert hrothgar['mention_count'] > 0, "mention_count 없음"
        assert len(hrothgar['contexts']) > 0, "contexts 없음"

        print(f"✅ 테스트 2 통과: Hrothgar context {len(hrothgar['contexts'])}개")
        print(f"   샘플: {hrothgar['contexts'][0]['text'][:100]}...")

    print("\n모든 테스트 통과!")
```

---

## 6. 166권 DB 매칭

### 목표
추출된 엔티티를 DB와 연결하고 text_mentions 생성

### 실행 방법

```python
# poc/scripts/cleanup/match_existing_books.py

import json
from pathlib import Path

CONTEXTS_DIR = Path("poc/data/book_contexts")

def match_book_entities():
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    context_files = list(CONTEXTS_DIR.glob("*_contexts.json"))
    print(f"처리할 책: {len(context_files)}권")

    total_matched = 0
    total_new = 0

    for f in context_files:
        data = json.load(open(f, 'r', encoding='utf-8'))
        book_id = data['book_id']
        title = data['title']

        # source 찾거나 생성
        cur.execute("SELECT id FROM sources WHERE title = %s", (title,))
        source = cur.fetchone()
        if not source:
            cur.execute("""
                INSERT INTO sources (title, source_type, external_id)
                VALUES (%s, 'gutenberg', %s)
                RETURNING id
            """, (title, book_id))
            source_id = cur.fetchone()['id']
        else:
            source_id = source['id']

        # persons 매칭
        for name, info in data['entities']['persons'].items():
            context = " ".join([c['text'][:200] for c in info['contexts'][:3]])

            # 1. DB에서 이름으로 검색
            cur.execute("""
                SELECT id, wikidata_id FROM persons
                WHERE name ILIKE %s
                LIMIT 1
            """, (name,))
            match = cur.fetchone()

            if match:
                entity_id = match['id']
                total_matched += 1
            else:
                # 2. 새 엔티티 생성 (unverified)
                cur.execute("""
                    INSERT INTO persons (name, verification_status, confidence_score)
                    VALUES (%s, 'unverified', 0.5)
                    RETURNING id
                """, (name,))
                entity_id = cur.fetchone()['id']
                total_new += 1

            # 3. text_mention 생성
            for ctx in info['contexts']:
                cur.execute("""
                    INSERT INTO text_mentions
                    (entity_type, entity_id, source_id, mention_text, context_text, chunk_index)
                    VALUES ('person', %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (entity_id, source_id, name, ctx['text'][:500], ctx['chunk_id']))

    conn.commit()
    print(f"\n매칭 완료: {total_matched}개 연결, {total_new}개 새로 생성")
    conn.close()

if __name__ == "__main__":
    match_book_entities()
```

### 테스트

```python
# poc/scripts/cleanup/test_match_books.py

def test_match_books():
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    # 테스트 1: text_mentions 생성됐나
    cur.execute("SELECT COUNT(*) FROM text_mentions WHERE entity_type = 'person'")
    count = cur.fetchone()[0]
    assert count > 0, "text_mentions 없음"
    print(f"✅ 테스트 1 통과: text_mentions {count:,}개")

    # 테스트 2: Beowulf 관련 mentions
    cur.execute("""
        SELECT p.name, s.title, tm.mention_text
        FROM text_mentions tm
        JOIN persons p ON tm.entity_id = p.id
        JOIN sources s ON tm.source_id = s.id
        WHERE s.title ILIKE '%beowulf%'
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row[0]} in {row[1]}: {row[2][:50]}...")

    conn.close()
    print("\n모든 테스트 통과!")
```

---

## 7. Richard 문제 해결

### 목표
동명이인 분리, context로 올바른 QID 연결

### 실행 방법

```python
# poc/scripts/cleanup/resolve_duplicates.py

def resolve_common_names():
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 흔한 이름 목록
    common_names = ['Richard', 'John', 'William', 'Henry', 'Charles', 'Louis', 'Frederick']

    for common_name in common_names:
        print(f"\n=== {common_name} 처리 ===")

        # QID 없는 것 찾기
        cur.execute("""
            SELECT p.id, p.name
            FROM persons p
            WHERE p.name ILIKE %s
            AND p.wikidata_id IS NULL
        """, (f"{common_name}%",))
        entities = cur.fetchall()

        print(f"  QID 없는 {common_name}: {len(entities)}개")

        for entity in entities:
            # context 가져오기
            cur.execute("""
                SELECT context_text FROM text_mentions
                WHERE entity_type = 'person' AND entity_id = %s
                LIMIT 3
            """, (entity['id'],))
            contexts = [r['context_text'] for r in cur.fetchall() if r['context_text']]
            context = " ".join(contexts)[:500] if contexts else ""

            if not context:
                print(f"    [{entity['id']}] {entity['name']} - context 없음, skip")
                continue

            # Wikidata 검색
            qid = search_wikidata_with_context(entity['name'], context)

            if qid:
                # 기존에 이 QID 있나 확인
                cur.execute("SELECT id FROM persons WHERE wikidata_id = %s", (qid,))
                existing = cur.fetchone()

                if existing:
                    # 합치기
                    print(f"    [{entity['id']}] {entity['name']} → 기존 {existing['id']} ({qid})와 합침")
                    merge_entities(cur, existing['id'], entity['id'])
                else:
                    # QID 업데이트
                    print(f"    [{entity['id']}] {entity['name']} → {qid}")
                    cur.execute("""
                        UPDATE persons SET wikidata_id = %s, verification_status = 'verified'
                        WHERE id = %s
                    """, (qid, entity['id']))
            else:
                print(f"    [{entity['id']}] {entity['name']} - Wikidata 매칭 실패")

    conn.commit()
    conn.close()

def search_wikidata_with_context(name, context):
    """context를 활용한 Wikidata 검색"""
    # 간단한 검색 (실제로는 더 정교해야 함)
    params = {
        'action': 'wbsearchentities',
        'search': name,
        'language': 'en',
        'limit': 5,
        'format': 'json'
    }
    resp = requests.get("https://www.wikidata.org/w/api.php", params=params)
    results = resp.json().get('search', [])

    if not results:
        return None

    # context에 나온 키워드로 필터링
    context_lower = context.lower()
    for r in results:
        desc = r.get('description', '').lower()
        # 간단한 매칭 (실제로는 LLM 사용)
        if any(keyword in context_lower for keyword in desc.split()[:5]):
            return r['id']

    # 첫 번째 결과 반환 (확신 없음)
    return None

if __name__ == "__main__":
    resolve_common_names()
```

### 테스트

```python
# poc/scripts/cleanup/test_resolve_duplicates.py

def test_resolve_duplicates():
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    # 테스트 1: Richard로 시작하는 것들 확인
    cur.execute("""
        SELECT name, wikidata_id, verification_status
        FROM persons
        WHERE name ILIKE 'richard%'
        ORDER BY name
        LIMIT 20
    """)
    print("Richard 목록:")
    for row in cur.fetchall():
        status = "✅" if row[1] else "❌"
        print(f"  {status} {row[0]} ({row[1] or 'no QID'}) - {row[2]}")

    # 테스트 2: verified 비율
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE verification_status = 'verified') as verified,
            COUNT(*) as total
        FROM persons
        WHERE name ILIKE 'richard%'
    """)
    stats = cur.fetchone()
    print(f"\nRichard verified: {stats[0]}/{stats[1]} ({stats[0]*100//stats[1] if stats[1] else 0}%)")

    conn.close()
```

---

## 전체 실행 순서

```bash
# 0. 전체 백업
pg_dump -U chaldeas chaldeas > backup_full.sql

# 1. QID 중복 합치기
python poc/scripts/cleanup/merge_qid_duplicates.py
python poc/scripts/cleanup/test_merge_qid.py

# 2. QID 없는 것 분석
python poc/scripts/cleanup/analyze_no_qid.py > analysis_no_qid.txt

# 3. 쓰레기 삭제
python poc/scripts/cleanup/delete_garbage.py           # dry run
python poc/scripts/cleanup/delete_garbage.py --execute
python poc/scripts/cleanup/test_delete_garbage.py

# 4. Wikidata 정보 보강
python poc/scripts/cleanup/enrich_from_wikidata.py
python poc/scripts/cleanup/test_enrich.py

# 5. 166권 context 역추적
python poc/scripts/cleanup/extract_book_contexts.py
python poc/scripts/cleanup/test_extract_contexts.py

# 6. 166권 DB 매칭
python poc/scripts/cleanup/match_existing_books.py
python poc/scripts/cleanup/test_match_books.py

# 7. Richard 문제 해결
python poc/scripts/cleanup/resolve_duplicates.py
python poc/scripts/cleanup/test_resolve_duplicates.py

# 최종 확인
python poc/scripts/cleanup/final_verification.py
```
