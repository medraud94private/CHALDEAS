# 지속적 파이프라인 가이드

> 새 책 추가할 때마다 사용하는 파이프라인

---

## 파이프라인 개요

```
새 책 선택 → 추출 → 매칭 → DB 저장 → 검증
     ↑                              ↓
     └────── 수동 검토 큐 ←─────────┘
```

---

## 1. 책 추출 파이프라인

### 위치
```
tools/book_extractor/
├── server.py              # 웹 UI 서버
├── entity_matcher.py      # 매칭 로직
├── wikidata_search.py     # Wikidata 검색 (새로 만들어야 함)
└── index.html             # 웹 UI
```

### 실행
```bash
cd tools/book_extractor
python server.py
# http://localhost:8200 접속
```

### 개선된 추출 프롬프트

```python
# tools/book_extractor/prompts.py

EXTRACTION_PROMPT_V2 = """
You are extracting historical entities from a book.

RULES:
1. Use FULL names with titles/epithets
   ✓ "Richard I of England"
   ✗ "Richard"

2. Include aliases if mentioned
   "Richard the Lionheart (also called Coeur de Lion)"

3. Add context for disambiguation
   - Time period
   - Role/occupation
   - Key events associated

4. For mythological/legendary figures, note it
   "Beowulf (legendary Geatish hero)"

OUTPUT FORMAT:
```json
{
  "persons": [
    {
      "name": "Richard I of England",
      "aliases": ["Richard the Lionheart", "Coeur de Lion"],
      "context": "King of England (1189-1199), led Third Crusade",
      "type": "historical",
      "time_hint": "1157-1199"
    },
    {
      "name": "Beowulf",
      "aliases": [],
      "context": "Legendary Geatish hero who slew Grendel",
      "type": "legendary",
      "time_hint": "6th century (legendary)"
    }
  ],
  "locations": [...],
  "events": [...]
}
```

TEXT TO ANALYZE:
{text}
"""
```

### 테스트

```python
# tools/book_extractor/test_extraction.py

def test_extraction_prompt():
    """새 프롬프트 테스트"""

    test_text = """
    King Richard, known as the Lionheart, led the Third Crusade
    against Saladin. He was born in 1157 and died in 1199.
    Richard was the son of Henry II of England.
    """

    result = extract_entities(test_text, prompt=EXTRACTION_PROMPT_V2)

    # 테스트 1: full name 추출
    persons = result.get('persons', [])
    richard = next((p for p in persons if 'Richard' in p['name']), None)

    assert richard is not None, "Richard 못 찾음"
    assert 'Lionheart' in richard['name'] or 'Lionheart' in richard.get('aliases', []), \
        "Lionheart alias 없음"
    print(f"✅ Richard: {richard}")

    # 테스트 2: context 있음
    assert richard.get('context'), "context 없음"
    assert 'Crusade' in richard['context'] or 'King' in richard['context'], \
        "context에 핵심 정보 없음"
    print(f"✅ Context: {richard['context']}")

    # 테스트 3: time_hint 있음
    assert richard.get('time_hint'), "time_hint 없음"
    print(f"✅ Time hint: {richard['time_hint']}")
```

---

## 2. Wikidata 검색 모듈

### 새로 만들어야 함

```python
# tools/book_extractor/wikidata_search.py

import requests
from typing import List, Optional, Dict
from dataclasses import dataclass

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


@dataclass
class WikidataCandidate:
    qid: str
    name: str
    description: str
    score: float  # 매칭 신뢰도


def search_wikidata(
    name: str,
    context: str = "",
    entity_type: str = "person",
    time_hint: str = "",
    limit: int = 5
) -> List[WikidataCandidate]:
    """
    Wikidata에서 엔티티 검색

    Args:
        name: 엔티티 이름
        context: 맥락 정보 (disambiguation용)
        entity_type: person/location/event
        time_hint: 시대 힌트 (예: "12th century", "1157-1199")
        limit: 최대 후보 수

    Returns:
        WikidataCandidate 리스트 (score 순 정렬)
    """

    # 1. 기본 검색
    params = {
        'action': 'wbsearchentities',
        'search': name,
        'language': 'en',
        'limit': limit * 2,  # 필터링할 거니까 여유있게
        'format': 'json',
        'type': 'item'
    }

    resp = requests.get(WIKIDATA_API, params=params)
    results = resp.json().get('search', [])

    if not results:
        return []

    candidates = []
    for r in results:
        qid = r['id']
        label = r.get('label', '')
        description = r.get('description', '')

        # 2. score 계산
        score = calculate_match_score(
            name=name,
            context=context,
            time_hint=time_hint,
            candidate_name=label,
            candidate_desc=description,
            entity_type=entity_type
        )

        candidates.append(WikidataCandidate(
            qid=qid,
            name=label,
            description=description,
            score=score
        ))

    # 3. score 순 정렬
    candidates.sort(key=lambda x: x.score, reverse=True)

    return candidates[:limit]


def calculate_match_score(
    name: str,
    context: str,
    time_hint: str,
    candidate_name: str,
    candidate_desc: str,
    entity_type: str
) -> float:
    """매칭 신뢰도 계산"""

    score = 0.0
    context_lower = context.lower()
    desc_lower = candidate_desc.lower()

    # 1. 이름 정확도 (0-0.4)
    if name.lower() == candidate_name.lower():
        score += 0.4
    elif name.lower() in candidate_name.lower():
        score += 0.3
    elif candidate_name.lower() in name.lower():
        score += 0.2

    # 2. context 매칭 (0-0.3)
    context_keywords = extract_keywords(context)
    desc_keywords = extract_keywords(candidate_desc)
    overlap = len(context_keywords & desc_keywords)
    score += min(overlap * 0.1, 0.3)

    # 3. 시대 매칭 (0-0.2)
    if time_hint:
        years = extract_years(time_hint)
        desc_years = extract_years(candidate_desc)
        if years and desc_years:
            # 시대가 비슷하면 가점
            if any(abs(y1 - y2) < 100 for y1 in years for y2 in desc_years):
                score += 0.2
            elif any(abs(y1 - y2) < 500 for y1 in years for y2 in desc_years):
                score += 0.1

    # 4. 타입 매칭 (0-0.1)
    if entity_type == 'person':
        person_keywords = ['king', 'queen', 'emperor', 'leader', 'writer', 'philosopher']
        if any(k in desc_lower for k in person_keywords):
            score += 0.1

    return min(score, 1.0)


def extract_keywords(text: str) -> set:
    """텍스트에서 중요 키워드 추출"""
    import re
    # 간단한 구현 - 실제로는 더 정교해야 함
    words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
    stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'also'}
    return set(words) - stopwords


def extract_years(text: str) -> List[int]:
    """텍스트에서 연도 추출"""
    import re
    years = []
    # 양수 연도
    for m in re.findall(r'\b(1[0-9]{3}|[1-9][0-9]{2})\b', text):
        years.append(int(m))
    # BCE
    for m in re.findall(r'(\d+)\s*BCE?', text, re.I):
        years.append(-int(m))
    return years


def get_best_match(
    name: str,
    context: str = "",
    time_hint: str = "",
    min_score: float = 0.5
) -> Optional[WikidataCandidate]:
    """가장 좋은 매칭 반환 (없으면 None)"""

    candidates = search_wikidata(name, context, time_hint=time_hint)

    if not candidates:
        return None

    best = candidates[0]
    if best.score >= min_score:
        return best

    return None
```

### 테스트

```python
# tools/book_extractor/test_wikidata_search.py

def test_wikidata_search():
    from wikidata_search import search_wikidata, get_best_match

    # 테스트 1: Richard the Lionheart
    candidates = search_wikidata(
        name="Richard the Lionheart",
        context="King of England, Third Crusade",
        time_hint="1157-1199"
    )
    print("Richard the Lionheart 후보:")
    for c in candidates:
        print(f"  {c.qid}: {c.name} ({c.score:.2f}) - {c.description}")

    assert any(c.qid == 'Q190112' for c in candidates), "Q190112 (Richard I) 못 찾음"
    print("✅ Richard I (Q190112) 찾음")

    # 테스트 2: 애매한 이름
    candidates = search_wikidata(
        name="Richard",
        context="King of England",
        time_hint="12th century"
    )
    print("\n'Richard' + context 후보:")
    for c in candidates[:3]:
        print(f"  {c.qid}: {c.name} ({c.score:.2f})")

    # 테스트 3: get_best_match
    best = get_best_match(
        name="Napoleon Bonaparte",
        context="Emperor of France, Waterloo",
        min_score=0.5
    )
    assert best is not None, "Napoleon 못 찾음"
    assert best.qid == 'Q517', f"Wrong QID: {best.qid}"
    print(f"\n✅ Napoleon: {best.qid} (score: {best.score:.2f})")


def test_edge_cases():
    from wikidata_search import get_best_match

    # 테스트 1: 존재하지 않는 인물
    result = get_best_match("Xyzzyplugh the Magnificent")
    assert result is None or result.score < 0.3, "존재하지 않는 인물에 매칭됨"
    print("✅ 존재하지 않는 인물: 매칭 안 됨")

    # 테스트 2: 신화적 인물
    result = get_best_match(
        name="Beowulf",
        context="legendary Geatish hero, slew Grendel"
    )
    print(f"Beowulf: {result}")
    # Beowulf는 Wikidata에 있음 (Q152)

    # 테스트 3: 동명이인 구분
    richard1 = get_best_match("Richard", context="Crusade, 12th century, Lionheart")
    richard3 = get_best_match("Richard", context="War of Roses, 15th century, hunchback")

    print(f"Richard (Crusade): {richard1.qid if richard1 else None}")
    print(f"Richard (Roses): {richard3.qid if richard3 else None}")

    if richard1 and richard3:
        assert richard1.qid != richard3.qid, "동명이인 구분 실패"
        print("✅ 동명이인 구분 성공")
```

---

## 3. 매칭 파이프라인

### 개선된 entity_matcher.py

```python
# tools/book_extractor/entity_matcher.py (개선)

from wikidata_search import get_best_match, WikidataCandidate
from typing import Optional, Dict, Any
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class MatchResult:
    matched: bool
    entity_id: int
    qid: Optional[str] = None
    method: str = ""  # 'exact', 'alias', 'wikidata', 'new_verified', 'new_unverified'
    confidence: float = 0.0
    created: bool = False


class EntityMatcherV2:
    """개선된 엔티티 매처"""

    def __init__(self):
        self.conn = psycopg2.connect(
            host='localhost', port=5432, dbname='chaldeas',
            user='chaldeas', password='chaldeas_dev'
        )

    def match(self, extracted: Dict[str, Any], entity_type: str = 'person') -> MatchResult:
        """
        추출된 엔티티를 DB와 매칭

        Args:
            extracted: {
                "name": "Richard I of England",
                "aliases": ["Richard the Lionheart"],
                "context": "King of England, Third Crusade",
                "time_hint": "1157-1199"
            }
            entity_type: 'person', 'location', 'event'

        Returns:
            MatchResult
        """
        name = extracted['name']
        aliases = extracted.get('aliases', [])
        context = extracted.get('context', '')
        time_hint = extracted.get('time_hint', '')

        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        # 1. DB에서 정확한 이름 매칭
        for search_name in [name] + aliases:
            cur.execute("""
                SELECT id, wikidata_id FROM persons
                WHERE name ILIKE %s AND wikidata_id IS NOT NULL
                LIMIT 1
            """, (search_name,))
            match = cur.fetchone()

            if match:
                return MatchResult(
                    matched=True,
                    entity_id=match['id'],
                    qid=match['wikidata_id'],
                    method='exact',
                    confidence=1.0
                )

        # 2. alias 테이블에서 검색
        for search_name in [name] + aliases:
            cur.execute("""
                SELECT p.id, p.wikidata_id
                FROM entity_aliases ea
                JOIN persons p ON ea.entity_id = p.id AND ea.entity_type = 'person'
                WHERE ea.alias ILIKE %s AND p.wikidata_id IS NOT NULL
                LIMIT 1
            """, (search_name,))
            match = cur.fetchone()

            if match:
                return MatchResult(
                    matched=True,
                    entity_id=match['id'],
                    qid=match['wikidata_id'],
                    method='alias',
                    confidence=0.95
                )

        # 3. Wikidata 검색
        wikidata_match = get_best_match(
            name=name,
            context=context,
            time_hint=time_hint,
            min_score=0.6
        )

        if wikidata_match and wikidata_match.score >= 0.6:
            qid = wikidata_match.qid

            # DB에서 QID로 검색
            cur.execute("""
                SELECT id FROM persons WHERE wikidata_id = %s
            """, (qid,))
            existing = cur.fetchone()

            if existing:
                # 이미 있음 → 연결
                entity_id = existing['id']
                created = False
            else:
                # 없음 → 새로 생성 (Wikidata에서 검증됨)
                cur.execute("""
                    INSERT INTO persons (name, wikidata_id, verification_status, confidence_score)
                    VALUES (%s, %s, 'verified', %s)
                    RETURNING id
                """, (wikidata_match.name, qid, wikidata_match.score))
                entity_id = cur.fetchone()['id']
                created = True
                self.conn.commit()

            # alias 저장
            for alias in aliases:
                self._save_alias(entity_id, alias, 'book_extraction')

            return MatchResult(
                matched=True,
                entity_id=entity_id,
                qid=qid,
                method='wikidata',
                confidence=wikidata_match.score,
                created=created
            )

        # 4. 매칭 실패 → unverified로 생성
        cur.execute("""
            INSERT INTO persons (name, verification_status, confidence_score)
            VALUES (%s, 'unverified', 0.3)
            RETURNING id
        """, (name,))
        entity_id = cur.fetchone()['id']
        self.conn.commit()

        # context 저장 (나중에 검토용)
        if context:
            cur.execute("""
                UPDATE persons SET description = %s WHERE id = %s
            """, (context[:500], entity_id))
            self.conn.commit()

        for alias in aliases:
            self._save_alias(entity_id, alias, 'book_extraction')

        return MatchResult(
            matched=False,
            entity_id=entity_id,
            method='new_unverified',
            confidence=0.3,
            created=True
        )

    def _save_alias(self, entity_id: int, alias: str, source: str):
        """alias 저장"""
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO entity_aliases (entity_type, entity_id, alias, alias_type)
            VALUES ('person', %s, %s, %s)
            ON CONFLICT (entity_type, entity_id, alias) DO NOTHING
        """, (entity_id, alias, source))
        self.conn.commit()

    def close(self):
        self.conn.close()
```

### 테스트

```python
# tools/book_extractor/test_entity_matcher_v2.py

def test_entity_matcher_v2():
    from entity_matcher import EntityMatcherV2

    matcher = EntityMatcherV2()

    # 테스트 1: 기존 DB에 있는 인물
    result = matcher.match({
        "name": "Napoleon Bonaparte",
        "context": "Emperor of France",
        "time_hint": "1769-1821"
    })
    print(f"Napoleon: {result}")
    assert result.matched, "Napoleon 매칭 실패"
    assert result.qid == 'Q517', f"Wrong QID: {result.qid}"
    print("✅ 테스트 1 통과: Napoleon 매칭")

    # 테스트 2: alias로 매칭
    result = matcher.match({
        "name": "Napoleon the Great",
        "context": "French Emperor"
    })
    print(f"Napoleon the Great: {result}")
    assert result.matched, "Napoleon alias 매칭 실패"
    print("✅ 테스트 2 통과: alias 매칭")

    # 테스트 3: Wikidata에서 찾기
    result = matcher.match({
        "name": "Saladin",
        "aliases": ["Salah ad-Din"],
        "context": "Sultan of Egypt, fought Richard in Crusade",
        "time_hint": "12th century"
    })
    print(f"Saladin: {result}")
    assert result.qid == 'Q187689' or result.matched, "Saladin 매칭 문제"
    print("✅ 테스트 3 통과: Wikidata 검색")

    # 테스트 4: 알 수 없는 인물 (unverified)
    result = matcher.match({
        "name": "Hrothgar of the Danes",
        "context": "King in Beowulf legend"
    })
    print(f"Hrothgar: {result}")
    assert result.method in ['wikidata', 'new_unverified'], "Hrothgar 처리 이상"
    print("✅ 테스트 4 통과: unknown 처리")

    matcher.close()
    print("\n모든 테스트 통과!")
```

---

## 4. 출처 추적 (text_mentions)

### 매칭 후 text_mention 저장

```python
# tools/book_extractor/mention_tracker.py

import psycopg2
from psycopg2.extras import RealDictCursor


class MentionTracker:
    """출처 추적 관리"""

    def __init__(self):
        self.conn = psycopg2.connect(
            host='localhost', port=5432, dbname='chaldeas',
            user='chaldeas', password='chaldeas_dev'
        )

    def record_mention(
        self,
        entity_type: str,
        entity_id: int,
        source_id: int,
        mention_text: str,
        context_text: str = "",
        chunk_index: int = None,
        confidence: float = 1.0
    ):
        """text_mention 기록"""
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO text_mentions
            (entity_type, entity_id, source_id, mention_text, context_text, chunk_index, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (entity_type, entity_id, source_id, mention_text[:500], context_text[:1000], chunk_index, confidence))
        self.conn.commit()

    def get_or_create_source(self, title: str, source_type: str = 'gutenberg', external_id: str = None) -> int:
        """source 가져오거나 생성"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT id FROM sources WHERE title = %s", (title,))
        source = cur.fetchone()

        if source:
            return source['id']

        cur.execute("""
            INSERT INTO sources (title, source_type, external_id)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (title, source_type, external_id))
        source_id = cur.fetchone()['id']
        self.conn.commit()
        return source_id

    def get_mentions_for_entity(self, entity_type: str, entity_id: int):
        """엔티티의 모든 출처 조회"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT tm.*, s.title as source_title
            FROM text_mentions tm
            JOIN sources s ON tm.source_id = s.id
            WHERE tm.entity_type = %s AND tm.entity_id = %s
            ORDER BY tm.created_at DESC
        """, (entity_type, entity_id))
        return cur.fetchall()

    def close(self):
        self.conn.close()
```

### 테스트

```python
# tools/book_extractor/test_mention_tracker.py

def test_mention_tracker():
    from mention_tracker import MentionTracker

    tracker = MentionTracker()

    # 테스트 1: source 생성
    source_id = tracker.get_or_create_source("Test Book", "test", "test_123")
    assert source_id > 0, "source 생성 실패"
    print(f"✅ Source created: {source_id}")

    # 테스트 2: mention 기록
    tracker.record_mention(
        entity_type='person',
        entity_id=1,  # 실제 존재하는 ID 사용
        source_id=source_id,
        mention_text="Napoleon led the army",
        context_text="The great general Napoleon led the army across the Alps.",
        chunk_index=5,
        confidence=0.95
    )
    print("✅ Mention recorded")

    # 테스트 3: mention 조회
    mentions = tracker.get_mentions_for_entity('person', 1)
    print(f"Mentions for entity 1: {len(mentions)}개")
    if mentions:
        print(f"  Latest: {mentions[0]['source_title']} - {mentions[0]['mention_text'][:50]}")

    tracker.close()
    print("\n모든 테스트 통과!")
```

---

## 5. 전체 파이프라인 통합

### 새 책 처리 전체 흐름

```python
# tools/book_extractor/process_book.py

from entity_matcher import EntityMatcherV2
from mention_tracker import MentionTracker
from prompts import EXTRACTION_PROMPT_V2
import json


def process_new_book(book_path: str, book_title: str, book_id: str):
    """
    새 책 전체 처리

    1. 추출
    2. 매칭
    3. 출처 기록
    4. 결과 저장
    """

    matcher = EntityMatcherV2()
    tracker = MentionTracker()

    # source 등록
    source_id = tracker.get_or_create_source(book_title, 'gutenberg', book_id)

    # 책 내용 로드 (ZIM에서)
    book_content = load_book_from_zim(book_path)

    results = {
        'book_id': book_id,
        'title': book_title,
        'entities': {
            'persons': [],
            'locations': [],
            'events': []
        },
        'stats': {
            'total': 0,
            'matched': 0,
            'new_verified': 0,
            'new_unverified': 0
        }
    }

    # 청크별 처리
    for chunk in split_into_chunks(book_content):
        # 추출 (개선된 프롬프트)
        extracted = extract_entities(chunk['text'], EXTRACTION_PROMPT_V2)

        # persons 매칭
        for person in extracted.get('persons', []):
            match_result = matcher.match(person, 'person')

            # 출처 기록
            tracker.record_mention(
                entity_type='person',
                entity_id=match_result.entity_id,
                source_id=source_id,
                mention_text=person['name'],
                context_text=chunk['text'][:500],
                chunk_index=chunk['index'],
                confidence=match_result.confidence
            )

            # 통계
            results['stats']['total'] += 1
            if match_result.matched:
                results['stats']['matched'] += 1
            elif match_result.method == 'new_verified':
                results['stats']['new_verified'] += 1
            else:
                results['stats']['new_unverified'] += 1

            results['entities']['persons'].append({
                'name': person['name'],
                'entity_id': match_result.entity_id,
                'qid': match_result.qid,
                'method': match_result.method,
                'confidence': match_result.confidence
            })

        # locations, events도 유사하게 처리...

    # 결과 저장
    output_file = f"results/{book_id}_processed.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    matcher.close()
    tracker.close()

    print(f"\n=== {book_title} 처리 완료 ===")
    print(f"Total: {results['stats']['total']}")
    print(f"Matched: {results['stats']['matched']}")
    print(f"New (verified): {results['stats']['new_verified']}")
    print(f"New (unverified): {results['stats']['new_unverified']}")

    return results
```

### 테스트

```python
# tools/book_extractor/test_process_book.py

def test_full_pipeline():
    """전체 파이프라인 테스트 (작은 책으로)"""

    # 테스트용 작은 책
    test_book = {
        'path': 'test_data/short_story.txt',
        'title': 'Test Story',
        'id': 'test_001'
    }

    results = process_new_book(
        test_book['path'],
        test_book['title'],
        test_book['id']
    )

    # 검증
    assert results['stats']['total'] > 0, "추출된 엔티티 없음"
    print(f"✅ 추출: {results['stats']['total']}개")

    # DB 확인
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM text_mentions
        WHERE source_id = (SELECT id FROM sources WHERE external_id = 'test_001')
    """)
    mention_count = cur.fetchone()[0]
    assert mention_count > 0, "text_mentions 없음"
    print(f"✅ text_mentions: {mention_count}개")

    conn.close()
    print("\n전체 파이프라인 테스트 통과!")
```

---

## 6. 수동 검토 시스템

### unverified 엔티티 검토

```python
# tools/book_extractor/review_queue.py

def get_review_queue(limit: int = 50):
    """검토 필요한 엔티티 목록"""
    conn = psycopg2.connect(...)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT p.id, p.name, p.description, p.confidence_score,
               COUNT(tm.id) as mention_count,
               array_agg(DISTINCT s.title) as sources
        FROM persons p
        LEFT JOIN text_mentions tm ON p.id = tm.entity_id AND tm.entity_type = 'person'
        LEFT JOIN sources s ON tm.source_id = s.id
        WHERE p.verification_status = 'unverified'
        GROUP BY p.id
        ORDER BY COUNT(tm.id) DESC, p.confidence_score DESC
        LIMIT %s
    """, (limit,))

    return cur.fetchall()


def approve_entity(entity_id: int, qid: str = None):
    """엔티티 승인"""
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    if qid:
        cur.execute("""
            UPDATE persons
            SET wikidata_id = %s, verification_status = 'verified', confidence_score = 1.0
            WHERE id = %s
        """, (qid, entity_id))
    else:
        # QID 없이 수동 승인
        cur.execute("""
            UPDATE persons
            SET verification_status = 'manual', confidence_score = 0.8
            WHERE id = %s
        """, (entity_id,))

    conn.commit()
    conn.close()


def reject_entity(entity_id: int):
    """엔티티 거부 (삭제)"""
    conn = psycopg2.connect(...)
    cur = conn.cursor()

    cur.execute("DELETE FROM text_mentions WHERE entity_type = 'person' AND entity_id = %s", (entity_id,))
    cur.execute("DELETE FROM entity_aliases WHERE entity_type = 'person' AND entity_id = %s", (entity_id,))
    cur.execute("DELETE FROM persons WHERE id = %s", (entity_id,))

    conn.commit()
    conn.close()
```

---

## 최종 체크리스트

### 파이프라인 구축 완료 기준

```
[ ] wikidata_search.py 구현
[ ] wikidata_search.py 테스트 통과
[ ] entity_matcher.py 개선
[ ] entity_matcher.py 테스트 통과
[ ] mention_tracker.py 구현
[ ] mention_tracker.py 테스트 통과
[ ] process_book.py 통합
[ ] 전체 파이프라인 테스트 통과
[ ] 검토 큐 UI (8200 서버에 추가)
```

### 사용법

```bash
# 1. 서버 시작
cd tools/book_extractor
python server.py

# 2. 브라우저에서 http://localhost:8200

# 3. 책 선택 → Extract → Match → 결과 확인

# 4. 수동 검토 필요한 것은 Review 탭에서 처리
```
