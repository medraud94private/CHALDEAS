# 책 Context 추적 개선 기획서

> 작성일: 2026-01-27
> 상태: 계획 중

---

## 1. 현재 상황

### 1.1 문제점

**Richard 문제**
- "Richard"라는 이름만 추출
- 역사상 Richard는 수천 명 존재
- 어떤 Richard인지 알 수 없음 → 잘못된 매칭

**현재 추출 파이프라인**
```
책 텍스트 → LLM → 이름만 추출 → 이름 기반 매칭 → 대부분 실패
```

**데이터 손실**
- 166권의 책에서 엔티티 추출 완료
- 하지만 `chunk_results`에 context가 있음에도 활용 안 함
- text_mentions 거의 비어있음

### 1.2 현재 데이터 구조

**extraction_results 파일 예시:**
```json
{
  "book_id": "Beowulf_981",
  "chunk_results": [
    {
      "chunk_id": 5,
      "text_preview": "Then Hrothgar, protector of Shieldings, gave the king...",
      "persons": ["Hrothgar"],
      "locations": ["Denmark"],
      "events": ["Battle of Ravenswood"]
    }
  ]
}
```

→ `text_preview`에 context가 있음! 이걸 활용해야 함

---

## 2. 목표

### 2.1 핵심 목표
1. **Context 복구**: 166권에서 추출된 엔티티의 context 역추적
2. **정확한 매칭**: context를 활용한 Wikidata 매칭
3. **출처 추적**: 모든 정보에 "어떤 책, 어떤 문장" 기록

### 2.2 성공 지표
- text_mentions 레코드 10,000개 이상 생성
- 매칭 정확도 80% 이상
- 주요 인물(Napoleon, Richard I 등) 완벽 매칭

---

## 3. 작업 계획

### Phase 1: Context 역추적 (Task 5)

**목표**: chunk_results에서 엔티티별 context 추출

**입력**:
```
poc/data/book_samples/extraction_results/*_extraction.json
```

**출력**:
```
poc/data/book_contexts/{book_id}_contexts.json
```

**출력 형식**:
```json
{
  "book_id": "Beowulf_981",
  "title": "Beowulf",
  "entities": {
    "persons": {
      "Hrothgar": {
        "name": "Hrothgar",
        "mention_count": 47,
        "contexts": [
          {
            "text": "Then Hrothgar, protector of Shieldings...",
            "chunk_id": 5
          },
          {
            "text": "Hrothgar spoke, helmet of Shieldings...",
            "chunk_id": 12
          }
        ]
      }
    }
  }
}
```

**스크립트**: `poc/scripts/cleanup/extract_book_contexts.py`

**검증**:
- Beowulf에서 Hrothgar context 추출 확인
- 각 책별 파일 생성 확인

---

### Phase 2: Wikidata 기반 매칭 (Task 6)

**목표**: context를 활용해 정확한 QID 매칭

**매칭 로직**:
```
1. 이름 + context로 Wikidata 검색
2. 후보 여러 개 반환
3. context와 description 비교
4. 가장 적합한 후보 선택
5. 신뢰도 점수 부여
```

**예시: "Richard" 매칭**

| 이름 | Context | Wikidata 후보 | 선택 |
|------|---------|---------------|------|
| Richard | "King of England, led Third Crusade" | Q190112 (Richard I) | ✅ |
| Richard | "Executed by Henry VII" | Q133028 (Richard III) | ✅ |
| Richard | "American physicist, Feynman diagrams" | Q39246 (Feynman) | ✅ |

**새 모듈**: `tools/book_extractor/wikidata_search.py`

```python
def search_wikidata_with_context(name: str, context: str) -> list[WikidataCandidate]:
    """
    Context를 활용한 Wikidata 검색

    Returns:
        후보 리스트 (QID, name, description, score)
    """

def match_best_candidate(name: str, context: str, candidates: list) -> MatchResult:
    """
    가장 적합한 후보 선택

    Returns:
        qid, confidence_score, match_reason
    """
```

**결과 처리**:
- `confidence >= 0.8`: 자동 매칭 (verified)
- `0.5 <= confidence < 0.8`: 검토 큐 (pending_review)
- `confidence < 0.5`: 미매칭 (unverified)

---

### Phase 3: text_mentions 생성 (Task 6 계속)

**목표**: 매칭된 엔티티와 책/문장 연결

**테이블 구조** (기존):
```sql
CREATE TABLE text_mentions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50),      -- 'person', 'location', 'event'
    entity_id INTEGER,            -- persons.id
    source_id INTEGER,            -- sources.id
    mention_text VARCHAR(500),    -- 원본 언급
    context_text TEXT,            -- 주변 문맥
    chunk_index INTEGER,          -- 책 내 위치
    confidence FLOAT DEFAULT 1.0
);
```

**생성 로직**:
```python
for book in books:
    source = get_or_create_source(book)
    for entity_name, contexts in book.entities.items():
        match = match_to_db_or_wikidata(entity_name, contexts)
        if match:
            for ctx in contexts:
                create_text_mention(
                    entity_type='person',
                    entity_id=match.db_id,
                    source_id=source.id,
                    mention_text=entity_name,
                    context_text=ctx.text,
                    chunk_index=ctx.chunk_id,
                    confidence=match.confidence
                )
```

---

### Phase 4: 동명이인 해결 (Task 7)

**문제**: 같은 이름, 다른 사람

**현재 상태**:
```sql
SELECT name, COUNT(*) FROM persons
WHERE name LIKE 'Richard%' AND wikidata_id IS NULL
-- 결과: 수백 개
```

**해결 전략**:

1. **Context 기반 분리**
   ```
   "Richard" in Beowulf → Richard I (Q190112)
   "Richard" in Shakespeare → Richard III (Q133028)
   ```

2. **흔한 이름 목록**
   ```python
   COMMON_NAMES = [
       'Richard', 'John', 'William', 'Henry', 'Charles',
       'Louis', 'Frederick', 'George', 'James', 'Edward'
   ]
   ```

3. **처리 우선순위**
   - mentions 많은 것부터
   - context 있는 것만
   - Wikidata 검색 가능한 것

**결과**:
- QID 부여 → verified
- QID 실패 but context 있음 → unverified + context 저장
- context 없음 → pending_deletion 검토

---

## 4. 새 파이프라인 설계

### 4.1 추출 프롬프트 개선

**현재 (문제)**:
```
Extract person names from this text.
```

**개선**:
```
Extract historical figures with full identification:

For each person mentioned:
1. Full name with titles: "Richard I of England" not just "Richard"
2. Context: What role/action in this passage
3. Time hint: Any century/era clues

Output format:
{
  "persons": [
    {
      "name": "Richard I of England",
      "context": "King who led Third Crusade",
      "time_hint": "12th century"
    }
  ]
}
```

### 4.2 매칭 파이프라인

```
추출된 엔티티
     ↓
┌─────────────────────────────────────┐
│ Stage 1: Wikidata 검색              │
│   name + context → QID 후보         │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│ Stage 2: 후보 평가                  │
│   description ↔ context 비교        │
│   신뢰도 점수 계산                  │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│ Stage 3: DB 연결                    │
│   QID로 DB 조회                     │
│   있음 → text_mention 추가          │
│   없음 → Wikidata에서 생성          │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│ Stage 4: Alias 저장                 │
│   원본 표기 → QID 매핑              │
│   "Richard the Lionheart" → Q190112 │
└─────────────────────────────────────┘
```

### 4.3 검토 큐

**자동 매칭 실패 시**:
```python
class ReviewQueue:
    def add_for_review(self, entity_name, context, candidates):
        """매칭 신뢰도 낮은 것 검토 큐에 추가"""

    def get_pending(self, limit=100):
        """검토 대기 목록 반환"""

    def approve(self, item_id, selected_qid):
        """수동 승인"""

    def reject(self, item_id, reason):
        """수동 거부"""
```

---

## 5. 구현 순서

### Week 1: Context 역추적

| 일자 | 작업 | 산출물 |
|------|------|--------|
| Day 1 | extract_book_contexts.py 완성 | 스크립트 |
| Day 2 | 166권 context 추출 실행 | book_contexts/*.json |
| Day 3 | 검증 및 통계 | 분석 리포트 |

### Week 2: Wikidata 매칭

| 일자 | 작업 | 산출물 |
|------|------|--------|
| Day 1-2 | wikidata_search.py 구현 | 새 모듈 |
| Day 3-4 | match_existing_books.py 실행 | DB 업데이트 |
| Day 5 | text_mentions 생성 확인 | 통계 리포트 |

### Week 3: 동명이인 해결

| 일자 | 작업 | 산출물 |
|------|------|--------|
| Day 1-2 | resolve_duplicates.py 구현 | 스크립트 |
| Day 3-4 | 흔한 이름 처리 | DB 업데이트 |
| Day 5 | 검토 큐 UI (선택) | 웹 인터페이스 |

---

## 6. 예상 결과

### 6.1 정량적 목표

| 지표 | 현재 | 목표 |
|------|------|------|
| text_mentions | ~0 | 50,000+ |
| 매칭된 persons | ~91K | 120K+ |
| 책 연결 persons | ~0 | 30,000+ |
| 한글명 보유 | 1,000 | 50,000+ |

### 6.2 정성적 목표

1. **출처 추적 가능**
   - "나폴레옹이 언급된 책들" 쿼리 가능
   - 각 정보의 출처 표시

2. **Richard 문제 해결**
   - "Richard I of England" ≠ "Richard III"
   - Context 기반 정확한 구분

3. **신규 책 처리 자동화**
   - 새 책 추가 시 자동 파이프라인
   - 높은 신뢰도 자동 매칭, 낮은 신뢰도 검토 큐

---

## 7. 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| Wikidata API 제한 | 중 | 중 | 캐싱, 배치 처리, 지연 |
| 매칭 정확도 낮음 | 중 | 높 | 보수적 임계값, 검토 큐 |
| 동명이인 구분 실패 | 높 | 중 | context 필수, 수동 검토 |
| 처리 시간 과다 | 중 | 저 | 병렬 처리, 배치 분할 |

---

## 8. 의존성

### 필요 조건
- [x] Task 1-3 완료 (DB 정리)
- [x] Wikidata API 접근 가능
- [ ] 166권 extraction_results 파일 존재 확인

### 확인 완료 ✅
```bash
ls poc/data/book_samples/extraction_results/*.json | wc -l
# 결과: 167개 (예상보다 1개 더 있음)
```

**파일 구조 확인** (Beowulf_981 예시):
```
- chunk_results: 60개 청크
- 각 청크: chunk_id, text_preview, persons, locations, events
- text_preview: 실제 텍스트 (context 역할)
```

**샘플 청크**:
```json
{
  "chunk_id": 1,
  "persons": ["Beowulf", "Healfdene", "Hrothgar", "Grendel", "Cain"],
  "text_preview": "Now Beowulf bode in the burg of the Scyldings..."
}
```

→ **Context 복구 가능 확인됨**

---

## 9. 스크립트 목록

### 일회성 작업
| 스크립트 | 용도 | 상태 |
|----------|------|------|
| extract_book_contexts.py | 166권 context 역추적 | 작성 필요 |
| match_existing_books.py | 166권 DB 매칭 | 작성 필요 |
| resolve_duplicates.py | 동명이인 해결 | 작성 필요 |

### 지속 사용
| 스크립트 | 용도 | 상태 |
|----------|------|------|
| wikidata_search.py | Wikidata 검색 함수 | 작성 필요 |
| entity_matcher_v2.py | 새 매칭 파이프라인 | 작성 필요 |
| mention_tracker.py | text_mentions 관리 | 작성 필요 |
| review_queue.py | 수동 검토 시스템 | 작성 필요 |

---

## 10. 다음 단계

1. **extraction_results 파일 확인**: 166권 존재 여부
2. **extract_book_contexts.py 작성**: Task 5 시작
3. **Beowulf로 파일럿**: 1권으로 전체 플로우 테스트
4. **전체 실행**: 검증 후 166권 처리
