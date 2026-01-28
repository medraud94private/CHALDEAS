# 이벤트 계층화 - 관계 후처리 파이프라인

**작성일**: 2026-01-28
**목적**: Book Extractor 파이프라인에 관계 분석 단계 추가

---

## 1. 현재 파이프라인

### 1.1 Book Extractor 흐름 (tools/book_extractor/server.py)

```
┌─────────────────────────────────────────────────────────────┐
│  1. ZIM 파일 읽기                                           │
│     └─ get_book_content_from_zim(path)                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Hierarchical Chunking                                   │
│     └─ get_hierarchical_chunks(content)                     │
│     └─ BOOK/CHAPTER 구조 자동 감지                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. LLM 엔티티 추출                                         │
│     └─ extract_chunk_with_retry(client, text, title, model) │
│     └─ 출력: {persons: [], locations: [], events: []}       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. 결과 저장                                               │
│     └─ {book_id}_extraction.json                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  5. run_post_processing() ← 여기에 추가!                    │
│     ├─ auto_context: context 추출                           │
│     ├─ auto_db_match: DB 엔티티 매칭                        │
│     └─ auto_relations: 관계 분석 (NEW)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 관계 분석 단계 추가

### 2.1 설정 추가

```python
# server.py 수정
post_process_settings = {
    "auto_context": True,     # 기존
    "auto_db_match": True,    # 기존
    "auto_relations": True,   # 신규: 관계 분석
}
```

### 2.2 run_post_processing 확장

```python
async def run_post_processing(book_id: str, title: str):
    """Run post-processing: context + DB match + relations"""

    # 1. 기존: Context 추출
    if post_process_settings["auto_context"]:
        # ... 기존 코드 ...

    # 2. 기존: DB 매칭
    if post_process_settings["auto_db_match"]:
        # ... 기존 코드 ...

    # 3. 신규: 관계 분석
    if post_process_settings["auto_relations"]:
        await analyze_book_relationships(book_id, title, conn)

    post_process_stats["last_processed"] = title
```

### 2.3 관계 분석 함수

```python
async def analyze_book_relationships(book_id: str, title: str, conn):
    """책에서 추출된 엔티티 간 관계 분석 및 업데이트"""

    # 1. 추출 결과 로드
    extraction_file = RESULTS_DIR / f"{safe_filename(book_id)}_extraction.json"
    with open(extraction_file, 'r') as f:
        extraction = json.load(f)

    persons = extraction.get("persons", [])
    events = extraction.get("events", [])
    locations = extraction.get("locations", [])
    chunk_results = extraction.get("chunk_results", [])

    # 2. DB에서 매칭된 엔티티 ID 조회
    matched_persons = get_matched_entity_ids("person", persons, conn)
    matched_events = get_matched_entity_ids("event", events, conn)

    # 3. 청크별 공출현 분석
    co_occurrences = analyze_co_occurrences(chunk_results)

    # 4. 관계 업데이트
    update_relationships(co_occurrences, conn)

    print(f"[Relations] {len(co_occurrences)} relationships analyzed")
```

---

## 3. 공출현 분석

### 3.1 청크 기반 공출현

```python
def analyze_co_occurrences(chunk_results: List[dict]) -> List[dict]:
    """청크별 엔티티 공출현 분석"""

    co_occurrences = defaultdict(lambda: {
        "count": 0,
        "chunks": [],
        "contexts": []
    })

    for chunk in chunk_results:
        chunk_id = chunk["chunk_id"]
        section = chunk["section"]
        persons = chunk.get("persons", [])
        events = chunk.get("events", [])

        # Person-Person 공출현
        for i, p1 in enumerate(persons):
            for p2 in persons[i+1:]:
                key = tuple(sorted([p1, p2]))
                co_occurrences[("person", "person", key)]["count"] += 1
                co_occurrences[("person", "person", key)]["chunks"].append(chunk_id)
                co_occurrences[("person", "person", key)]["contexts"].append(
                    chunk.get("text_preview", "")[:100]
                )

        # Person-Event 공출현
        for person in persons:
            for event in events:
                key = (person, event)
                co_occurrences[("person", "event", key)]["count"] += 1
                co_occurrences[("person", "event", key)]["chunks"].append(chunk_id)

    return list(co_occurrences.items())
```

### 3.2 관계 강도 계산

```python
def calculate_relationship_strength(co_occurrence: dict) -> int:
    """공출현 데이터로 관계 강도 (1-5) 계산"""

    count = co_occurrence["count"]
    chunk_spread = len(set(co_occurrence["chunks"]))  # 분포된 청크 수

    # 공출현 횟수 기반
    if count >= 10:
        base_strength = 5
    elif count >= 5:
        base_strength = 4
    elif count >= 3:
        base_strength = 3
    elif count >= 2:
        base_strength = 2
    else:
        base_strength = 1

    # 여러 청크에 분포하면 보너스
    if chunk_spread >= 5:
        base_strength = min(5, base_strength + 1)

    return base_strength
```

---

## 4. 관계 업데이트

### 4.1 기존 관계 확인 및 업데이트

```python
def update_relationships(co_occurrences: List, conn):
    """분석된 공출현을 DB 관계로 업데이트"""

    cur = conn.cursor()

    for (type1, type2, key), data in co_occurrences:
        if type1 == "person" and type2 == "person":
            update_person_relationship(key[0], key[1], data, cur)
        elif type1 == "person" and type2 == "event":
            update_person_event_relationship(key[0], key[1], data, cur)

    conn.commit()


def update_person_relationship(person1: str, person2: str, data: dict, cur):
    """인물 간 관계 업데이트"""

    # DB에서 인물 ID 조회
    cur.execute("SELECT id FROM persons WHERE name = %s", (person1,))
    p1_result = cur.fetchone()
    cur.execute("SELECT id FROM persons WHERE name = %s", (person2,))
    p2_result = cur.fetchone()

    if not p1_result or not p2_result:
        return

    p1_id, p2_id = p1_result[0], p2_result[0]
    strength = calculate_relationship_strength(data)

    # 기존 관계 확인
    cur.execute("""
        SELECT strength, confidence FROM person_relationships
        WHERE person_id = %s AND related_person_id = %s
    """, (p1_id, p2_id))
    existing = cur.fetchone()

    if existing:
        # 기존 관계 강화
        old_strength, old_conf = existing
        new_strength = min(5, max(old_strength, strength))
        new_conf = min(0.99, old_conf + 0.05)  # 증거 추가로 confidence 상승

        cur.execute("""
            UPDATE person_relationships
            SET strength = %s, confidence = %s
            WHERE person_id = %s AND related_person_id = %s
        """, (new_strength, new_conf, p1_id, p2_id))
    else:
        # 새 관계 생성
        cur.execute("""
            INSERT INTO person_relationships
            (person_id, related_person_id, relationship_type, strength, confidence)
            VALUES (%s, %s, %s, %s, %s)
        """, (p1_id, p2_id, "associated", strength, 0.5))
```

---

## 5. LLM 기반 관계 분석 (선택적)

### 5.1 관계 유형 추론

공출현만으로는 관계 유형(teacher, rival, etc.)을 알 수 없음.
LLM에게 추가 질문:

```python
async def infer_relationship_type(person1: str, person2: str, contexts: List[str]) -> dict:
    """LLM으로 관계 유형 추론"""

    prompt = f"""
두 인물의 관계를 분석해주세요.

인물 1: {person1}
인물 2: {person2}

이들이 함께 언급된 맥락:
{chr(10).join(contexts[:3])}

다음 중 가장 적절한 관계 유형을 선택하세요:
- teacher/student: 스승-제자
- allies: 동맹/협력
- rivals: 경쟁/대립
- family: 가족/친척
- colleagues: 동료
- ruler/subject: 군주-신하
- unknown: 알 수 없음

JSON으로 답변: {{"type": "...", "confidence": 0.0-1.0, "reasoning": "..."}}
"""

    response = await call_llm(prompt)
    return parse_json_response(response)
```

### 5.2 배치 처리

모든 관계에 LLM을 호출하면 비용이 많이 듦.
선별적으로 처리:

```python
def should_analyze_with_llm(co_occurrence: dict) -> bool:
    """LLM 분석이 필요한지 판단"""

    # 공출현 3회 이상이고, 관계 유형이 없는 경우만
    if co_occurrence["count"] < 3:
        return False

    # 이미 관계 유형이 있으면 스킵
    if has_relationship_type(co_occurrence):
        return False

    return True
```

---

## 6. 통계 및 모니터링

### 6.1 관계 분석 통계

```python
relation_stats = {
    "books_processed": 0,
    "relationships_created": 0,
    "relationships_updated": 0,
    "llm_inferences": 0,
    "last_processed": None,
}
```

### 6.2 API 엔드포인트

```python
@app.get("/api/postprocess/relations/stats")
async def get_relation_stats():
    """관계 분석 통계 조회"""
    return relation_stats


@app.post("/api/postprocess/relations/settings")
async def update_relation_settings(auto_relations: bool = None, use_llm: bool = None):
    """관계 분석 설정 변경"""
    if auto_relations is not None:
        post_process_settings["auto_relations"] = auto_relations
    if use_llm is not None:
        post_process_settings["use_llm_for_relations"] = use_llm
    return post_process_settings
```

---

## 7. 재귀적 개선 효과

### 7.1 문서 처리 누적 효과

```
문서 1 처리 후:
  소크라테스-플라톤: strength 2, confidence 0.5

문서 2 처리 후 (플라톤 대화편):
  소크라테스-플라톤: strength 4, confidence 0.6 (↑)

문서 3 처리 후 (철학사 개론):
  소크라테스-플라톤: strength 5, confidence 0.7 (↑)
  새 발견: 플라톤-아리스토텔레스 (strength 3)

...반복할수록 관계망 정교화
```

### 7.2 모순 발견

```python
def check_contradictions(new_evidence: dict, existing_rel: dict) -> bool:
    """새 증거가 기존 관계와 모순되는지 확인"""

    # 예: 기존에 "allies"인데 새 문서에서 "rivals"로 나오면
    if existing_rel["type"] == "allies" and new_evidence.get("suggests") == "rivals":
        flag_for_review(existing_rel, new_evidence)
        return True

    return False
```

---

## 8. 구현 체크리스트

### Phase 1: 기본 통합
- [ ] `post_process_settings`에 `auto_relations` 추가
- [ ] `run_post_processing`에 관계 분석 단계 추가
- [ ] `analyze_co_occurrences` 함수 구현
- [ ] `update_relationships` 함수 구현

### Phase 2: 강화
- [ ] 관계 강도 계산 로직 개선
- [ ] confidence 업데이트 로직
- [ ] 통계 수집 및 API

### Phase 3: LLM 통합 (선택)
- [ ] 관계 유형 추론 프롬프트
- [ ] 배치 처리 최적화
- [ ] 비용 추적

---

## 9. 관련 파일

| 파일 | 수정 내용 |
|------|----------|
| `tools/book_extractor/server.py` | `run_post_processing` 확장 |
| `tools/book_extractor/relation_analyzer.py` | 신규: 관계 분석 모듈 |
| `backend/app/models/associations.py` | 참조: 기존 관계 테이블 |
