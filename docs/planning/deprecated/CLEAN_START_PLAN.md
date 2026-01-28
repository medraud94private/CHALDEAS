# CHALDEAS 클린 스타트 플랜

## 우리가 가진 원본 자료

### 1. Wikidata (API)
- **신뢰도**: 최상
- **내용**: 전 세계 지식 그래프, 1억+ 엔티티
- **장점**: QID로 고유 식별, 다국어 지원, 관계 정보
- **용도**: Primary Source of Truth

### 2. Gutenberg ZIM (206GB)
- **파일**: `data/kiwix/gutenberg_en_all.zim`
- **내용**: ~80,000권 공개 도서
- **장점**: 원문 텍스트 접근 가능
- **용도**: 소스 텍스트, 인용 추출

### 3. FGO 서번트 데이터
- **내용**: 게임 내 역사적 인물 목록
- **용도**: 우선순위 인물 목록 (누구를 먼저 처리할지)

### 4. 현재 DB (쓰레기)
- **상태**: 286,566 persons 중 65%가 QID 없음, 중복 다수
- **처리**: 버리거나 QID 있는 것만 salvage

---

## 최종 목표

### 뭘 만들려는 건가?

**역사 지식 시스템**:
1. "나폴레옹이 누구야?" → 정확한 정보 + 출처
2. "나폴레옹이 언급된 책은?" → Beowulf에서는 안 나옴, 전쟁과 평화에서 나옴
3. "워털루 전투 관련 인물은?" → 나폴레옹, 웰링턴, 블뤼허...

### 핵심 요구사항

1. **정확한 식별**: "Napoleon" = Q517 (나폴레옹 보나파르트), 다른 Napoleon들과 구분
2. **출처 추적**: 모든 정보는 어디서 왔는지 알 수 있어야 함
3. **중복 없음**: 한 인물 = 한 레코드

---

## 새로운 설계 원칙

### 원칙 1: Wikidata QID가 Primary Key

```
모든 엔티티는 QID로 식별
QID 없으면 DB에 안 넣음 (또는 별도 "미확인" 테이블)
```

**이유**:
- Wikidata가 이미 disambiguation 해놓음
- Q517 = Napoleon Bonaparte, Q7721 = Napoleon III
- 우리가 다시 할 필요 없음

### 원칙 2: 이름은 Alias일 뿐

```
persons 테이블:
  - id (PK, 우리 내부용)
  - wikidata_id (UNIQUE, NOT NULL) ← 핵심
  - canonical_name (Wikidata에서 가져온 공식 이름)

entity_aliases 테이블:
  - entity_id → persons.id
  - alias ("Napoleon the Great", "나폴레옹", "ナポレオン")
  - language
  - source (wikidata, book_extraction, manual)
```

### 원칙 3: 책 추출은 Wikidata 검색 후 연결

```
책에서 "Napoleon" 추출
  ↓
Wikidata API 검색: "Napoleon" + context
  ↓
결과: Q517 (Napoleon Bonaparte), Q7721 (Napoleon III)...
  ↓
context로 판단해서 Q517 선택
  ↓
DB에 Q517 있으면 연결, 없으면 Q517 정보로 새로 생성
```

---

## 새로운 데이터 플로우

### Phase 1: 깨끗한 Base DB 구축

```
1. 현재 DB에서 QID 있는 것만 추출
2. QID 기준으로 중복 제거 (merge)
3. Wikidata에서 기본 정보 보강 (birth, death, description)
```

**결과**: QID로 식별되는 깨끗한 base

### Phase 2: FGO 서번트 기준 우선순위 인물

```
1. FGO 서번트 목록 로드
2. 각 서번트의 Wikidata QID 확인
3. DB에 없으면 Wikidata에서 가져와서 추가
```

**결과**: 최소한 FGO 관련 인물은 확실히 있음

### Phase 3: 책 추출 개선

```
1. 책에서 엔티티 추출 (개선된 프롬프트)
   - full name + context 포함

2. 각 엔티티에 대해:
   - Wikidata API 검색
   - 후보 중 context로 best match 선택
   - QID 확정

3. DB 연결:
   - QID로 DB 조회
   - 있으면 → text_mention 추가 (출처 기록)
   - 없으면 → Wikidata에서 정보 가져와서 새 레코드 생성
```

**결과**: 책에서 추출한 모든 엔티티가 QID로 식별됨

### Phase 4: 출처 추적 (text_mentions)

```
text_mentions 테이블:
  - entity_id (QID 기반 엔티티)
  - source_id (어떤 책)
  - mention_text ("Napoleon led his army")
  - context_text (주변 문장)
  - chunk_position (책 내 위치)
```

**결과**: "이 엔티티는 어떤 책에서 언급됐나?" 쿼리 가능

---

## 구체적 실행 계획

### Step 1: DB 정리 (1일)

```sql
-- QID 있는 persons만 남기고 중복 제거
-- 또는 새 테이블로 migration
```

### Step 2: Wikidata 검색 함수 구현 (1일)

```python
def search_wikidata(name: str, context: str, entity_type: str) -> Optional[str]:
    """
    Wikidata에서 검색하고 QID 반환
    context를 활용해서 disambiguation
    """
    # Wikidata API 호출
    # 후보 중 best match 선택
    return qid
```

### Step 3: 책 추출 프롬프트 개선 (1일)

```python
prompt = """
Extract historical entities with FULL identification.

Rules:
1. Use complete names: "Richard I of England" not "Richard"
2. Include titles/epithets: "the Lionheart", "the Great"
3. Add context: role, time period, key events

Output format:
{
  "persons": [
    {
      "extracted_name": "Richard the Lionheart",
      "context": "King of England who led the Third Crusade",
      "time_hint": "12th century"
    }
  ]
}
"""
```

### Step 4: 매칭 파이프라인 재구현 (2일)

```python
def match_entity(extracted: dict) -> MatchResult:
    # 1. Wikidata 검색
    qid = search_wikidata(
        name=extracted["extracted_name"],
        context=extracted["context"],
        entity_type="person"
    )

    if not qid:
        return MatchResult(matched=False, reason="not_in_wikidata")

    # 2. DB에서 QID로 조회
    entity = db.get_by_qid(qid)

    if entity:
        # 3a. 있으면 연결
        return MatchResult(matched=True, entity_id=entity.id, qid=qid)
    else:
        # 3b. 없으면 Wikidata에서 정보 가져와서 생성
        wikidata_info = fetch_wikidata_entity(qid)
        new_entity = db.create_from_wikidata(wikidata_info)
        return MatchResult(matched=True, entity_id=new_entity.id, qid=qid, created=True)
```

### Step 5: 기존 166권 재처리 (진행 중 가능)

```
옵션 A: 재추출 (깔끔, 느림)
옵션 B: 기존 데이터 + Wikidata 검색 (빠름)
```

---

## 최종 결과물

### DB 구조

```
persons
├── id (PK)
├── wikidata_id (UNIQUE, NOT NULL) ← 핵심
├── name (canonical)
├── birth_year, death_year
├── description
└── embedding (for search)

entity_aliases
├── entity_id → persons
├── alias
├── language
└── source

text_mentions
├── entity_id → persons
├── source_id → sources
├── mention_text
├── context_text
└── position

sources
├── id
├── title
├── type (book, wikipedia, manual)
└── gutenberg_id / zim_path
```

### 쿼리 예시

```sql
-- "나폴레옹이 언급된 책들"
SELECT s.title, tm.mention_text, tm.context_text
FROM text_mentions tm
JOIN persons p ON tm.entity_id = p.id
JOIN sources s ON tm.source_id = s.id
WHERE p.wikidata_id = 'Q517';

-- "워털루 전투 관련 인물들"
SELECT p.name, p.wikidata_id
FROM persons p
JOIN person_events pe ON p.id = pe.person_id
JOIN events e ON pe.event_id = e.id
WHERE e.wikidata_id = 'Q48314';  -- Battle of Waterloo
```

---

## 요약

| 항목 | Before (현재) | After (목표) |
|------|--------------|-------------|
| 식별자 | 이름 기반, 중복 다수 | QID 기반, 중복 없음 |
| 신뢰도 | 65% QID 없음 | 100% QID 있음 |
| 추출 | 이름만 | 이름 + context |
| 매칭 | embedding 유사도 | Wikidata 검색 |
| 출처 | 없음 | text_mentions |
