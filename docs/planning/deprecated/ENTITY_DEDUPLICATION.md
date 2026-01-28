# Entity Deduplication & Normalization

> **Status**: Active
> **Date**: 2026-01-26
> **Supersedes**: `ENTITY_NORMALIZATION.md`, `v2/ENTITY_MATCHING_STRATEGY.md`

---

## 1. 현황 분석

### 1.1 중복 규모

```
Total persons: 286,609
With wikidata_id: 101,968
Unique wikidata_ids: 91,596
Potential duplicates: 10,372 (동일 QID, 다른 레코드)
```

### 1.2 중복 사례 (상위)

| Wikidata QID | 중복 수 | 예시 |
|--------------|--------|------|
| Q517 (Napoleon) | 23 | Napoleon, Napoléon Bonaparte, Bonaparte, Napoleon the Great... |
| Q302 (Michelangelo) | 16 | - |
| Q692 (Shakespeare) | 13 | - |
| Q8409 (Alexander the Great) | 1 | 정상 (단, 오타 레코드 별도 존재) |

### 1.3 중복 유형

1. **QID 중복**: 동일 wikidata_id, 다른 name → 병합 필요
2. **오타/변형**: `Alex ander the Great` → 정규화 필요
3. **QID 없음**: wikidata_id = NULL인 레코드 중 중복 → 탐지 필요

---

## 2. 기술 스택 (확정)

| 구성요소 | 선택 | 근거 |
|---------|------|------|
| **Embedding** | `text-embedding-3-small` (OpenAI) | 이미 백엔드에서 사용 중, 1536 dim |
| **Vector Store** | pgvector | 이미 구축됨 |
| **LLM (1차)** | `gemma2:9b` (Ollama) | 로컬, 무료, 검증용 |
| **LLM (폴백)** | `gpt-5.1-chat-latest` | 복잡한 케이스 |
| **String Matching** | pg_trgm + rapidfuzz | PostgreSQL 내장 + Python |

---

## 3. 중복 정리 파이프라인

### Phase 1: QID 기반 병합 (확실한 중복)

```python
def merge_by_wikidata_id():
    """동일 wikidata_id를 가진 레코드 병합"""

    duplicates = db.execute("""
        SELECT wikidata_id, array_agg(id) as ids, array_agg(name) as names
        FROM persons
        WHERE wikidata_id IS NOT NULL
        GROUP BY wikidata_id
        HAVING COUNT(*) > 1
    """)

    for dup in duplicates:
        # 대표 이름 선정 (가장 일반적인 영어명)
        canonical = select_canonical_name(dup.names)
        primary_id = dup.ids[0]

        # 나머지를 alias로 저장
        for i, name in enumerate(dup.names):
            if name != canonical:
                save_alias(primary_id, name, alias_type='wikidata_variant')

        # 대표 레코드 업데이트
        update_person(primary_id, name=canonical)

        # 중복 레코드의 관계 이전 후 삭제
        for other_id in dup.ids[1:]:
            transfer_relationships(from_id=other_id, to_id=primary_id)
            delete_person(other_id)
```

**예상 결과**: ~10,000개 레코드 정리

### Phase 2: 임베딩 기반 후보 탐지 (QID 없는 중복)

```python
def find_potential_duplicates():
    """wikidata_id 없는 레코드 중 중복 후보 탐지"""

    orphans = db.query(Person).filter(Person.wikidata_id == None).all()

    for person in orphans:
        # 임베딩 유사도로 후보 검색
        candidates = vector_store.search_similar(
            embed(person.name),
            content_type="person",
            min_similarity=0.85,
            limit=5
        )

        if candidates:
            # LLM 검증
            result = verify_with_llm(person, candidates[0])
            if result.decision == "SAME":
                queue_for_merge(person.id, candidates[0].id, result.confidence)
```

### Phase 3: 수동 검토 큐

```sql
CREATE TABLE merge_queue (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES persons(id),
    target_id INTEGER REFERENCES persons(id),
    confidence FLOAT,
    method VARCHAR(50),  -- 'embedding', 'fuzzy', 'llm'
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    reviewed_at TIMESTAMP
);
```

---

## 4. 신규 엔티티 매칭 파이프라인

새로 추출된 이름이 기존 DB와 매칭되는지 확인:

```
[신규 이름]
    │
    ▼
┌─────────────────────────┐
│ 1. Exact Match          │ ─── name 일치 → Done (conf: 1.0)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ 2. Alias Match          │ ─── entity_aliases 테이블 → Done (conf: 0.95)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ 3. Wikidata QID Lookup  │ ─── 이름으로 Wikidata 검색 → QID 획득
│                         │     DB에 동일 QID 있으면 → Done (conf: 0.98)
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ 4. Embedding Similarity │ ─── text-embedding-3-small
│    (pgvector)           │     cosine > 0.9 → 후보 목록 생성
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ 5. LLM Verification     │ ─── gemma2:9b (로컬)
│                         │     "같은 인물인가?" → 최종 판정
└─────────────────────────┘
    │
    ▼
[매칭 결과] → 성공 시 alias 저장 (학습 루프)
```

### 4.1 규칙 기반 전처리 (최소화)

```python
# 타이틀만 제거 (수식어는 건드리지 않음)
TITLES = ['sir ', 'king ', 'queen ', 'lord ', 'lady ', 'prince ', 'princess ',
          'emperor ', 'empress ', 'pope ', 'saint ', 'st. ']

def normalize_title(name: str) -> str:
    """타이틀만 제거, 수식어는 유지"""
    lower = name.lower().strip()
    for title in TITLES:
        if lower.startswith(title):
            return name[len(title):].strip()
    return name

# 주의: "the Great", "of Macedon" 같은 수식어는 제거하지 않음
# → Wikidata alias로 처리
```

### 4.2 학습 루프

```python
def learn_from_match(extracted_name: str, matched_id: int, confidence: float):
    """성공적 매칭을 alias로 저장"""

    # 이미 있으면 skip
    if alias_exists(matched_id, extracted_name):
        return

    # 새 alias 저장
    db.execute("""
        INSERT INTO entity_aliases (entity_type, entity_id, alias, alias_type, source, confidence)
        VALUES ('person', %s, %s, 'learned', 'auto_matched', %s)
    """, (matched_id, extracted_name, confidence))
```

---

## 5. 데이터 구조

### 5.1 entity_aliases 테이블

```sql
CREATE TABLE entity_aliases (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- 'person', 'location', 'event'
    entity_id INTEGER NOT NULL,
    alias VARCHAR(255) NOT NULL,
    alias_type VARCHAR(50),  -- 'wikidata', 'historical', 'learned', 'wikidata_variant'
    source VARCHAR(100),     -- 'wikidata', 'auto_matched', 'manual'
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(entity_type, entity_id, alias)
);

CREATE INDEX idx_alias_lookup ON entity_aliases(LOWER(alias));
CREATE INDEX idx_alias_entity ON entity_aliases(entity_type, entity_id);
```

### 5.2 대표 이름 선정 기준

```python
def select_canonical_name(names: list[str]) -> str:
    """대표 이름 선정"""

    scores = []
    for name in names:
        score = 0

        # 영어 알파벳만 있으면 +10
        if name.isascii():
            score += 10

        # 특수문자 없으면 +5
        if name.replace(' ', '').isalnum():
            score += 5

        # 적당한 길이 (10-30자) +5
        if 10 <= len(name) <= 30:
            score += 5

        # "the Great", "of ..." 같은 수식어 있으면 +3 (구분력)
        if ' the ' in name.lower() or ' of ' in name.lower():
            score += 3

        scores.append((name, score))

    return max(scores, key=lambda x: x[1])[0]
```

---

## 6. 책 단위 처리 파이프라인

### 6.1 핵심 원칙

**"한 권 병합 → 확정 → 다음 권"**

- 전체 DB 정리 먼저가 아님
- 책 한 권씩 처리하면서 점진적으로 DB 품질 개선
- Person, Location, Event 모두 동일한 파이프라인

### 6.2 책 단위 처리 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                    책 1권 처리                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [1] 책에서 엔티티 추출                                       │
│      - persons: ["Napoleon", "Josephine", "Wellington"]      │
│      - locations: ["Waterloo", "Paris", "Elba"]              │
│      - events: ["Battle of Waterloo", "Coronation"]          │
│                                                              │
│  [2] 각 엔티티 매칭 (EntityMatcher)                           │
│      ┌────────────────────────────────────────────┐          │
│      │ "Napoleon"                                 │          │
│      │   → Exact? ✗                              │          │
│      │   → Alias? ✗                              │          │
│      │   → Wikidata? Q517 → DB에 있음!           │          │
│      │   → 매칭: person_id=26                    │          │
│      └────────────────────────────────────────────┘          │
│                                                              │
│  [3] 매칭 결과 리뷰                                           │
│      ┌────────────────────────────────────────────┐          │
│      │ MATCHED (wikidata):                       │          │
│      │   "Napoleon" → Napoleon (id=26) [conf=0.98]│          │
│      │   "Josephine" → Joséphine (id=89) [0.95]  │          │
│      │                                            │          │
│      │ NEW (no match):                           │          │
│      │   "General Cambronne" → 신규 생성 예정     │          │
│      └────────────────────────────────────────────┘          │
│                                                              │
│  [4] 확정 (Commit)                                           │
│      - 매칭된 것 → alias 저장 ("Napoleon" → id=26)           │
│      - 신규 → 레코드 생성 + embedding 저장                   │
│      - Source 연결                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    [다음 책으로]
```

### 6.3 점진적 품질 개선

```
책 1권 처리 후:
  - alias: "Napoleon" → id=26
  - alias: "Josephine" → id=89

책 2권 처리 시:
  - "Napoléon Bonaparte" 등장
  - Alias 매칭 실패 → Wikidata Q517 → id=26 매칭!
  - alias 추가: "Napoléon Bonaparte" → id=26

책 10권 처리 후:
  - Napoleon 관련 alias 10개 축적
  - 이후 책에서 빠른 매칭
```

### 6.4 QID 기반 기존 중복 처리

책 처리 중 QID 중복 발견 시:

```python
# "Napoléon" 매칭 시도 → Wikidata Q517
# DB 검색: Q517인 레코드가 여러 개?

existing = db.query(Person).filter(Person.wikidata_id == 'Q517').all()
# [id=26 "Napoleon", id=124769 "Napoleon Bonaparte", id=141296 "Napoleon the Great", ...]

if len(existing) > 1:
    # 자동 병합 트리거
    primary = select_primary(existing)  # id=26 선택
    for other in existing[1:]:
        save_alias(primary.id, other.name)
        transfer_relationships(other.id, primary.id)
        delete_person(other.id)
```

→ **책 처리하면서 자연스럽게 기존 중복도 정리됨**

### 6.5 EntityMatcher 서비스

```python
# backend/app/services/entity_matching/matcher.py

class EntityMatcher:
    """책 import 시 사용하는 통합 매칭 서비스 (Person/Location/Event)"""

    def __init__(self, session, embedding_service, wikidata_client):
        self.session = session
        self.embedding = embedding_service
        self.wikidata = wikidata_client

    def match(self, entity_type: str, name: str, context: str = None) -> MatchResult:
        """
        통합 5단계 매칭 파이프라인

        Args:
            entity_type: 'person', 'location', 'event'
            name: 엔티티 이름
            context: 문맥 (LLM 검증용)

        Returns:
            MatchResult(matched, entity_id, confidence, method)
        """
        model = self._get_model(entity_type)  # Person, Location, Event

        # 1. Exact match
        entity = self._exact_match(model, name)
        if entity:
            return MatchResult(True, entity.id, 1.0, 'exact')

        # 2. Alias match
        entity = self._alias_match(entity_type, name)
        if entity:
            return MatchResult(True, entity.id, 0.95, 'alias')

        # 3. Wikidata QID (+ 기존 중복 자동 병합)
        qid = self.wikidata.search(name, entity_type)
        if qid:
            entities = self._find_by_qid(model, qid)
            if entities:
                if len(entities) > 1:
                    # 중복 발견 → 자동 병합
                    primary = self._merge_duplicates(entity_type, entities)
                else:
                    primary = entities[0]
                self._learn_alias(entity_type, primary.id, name)
                return MatchResult(True, primary.id, 0.98, 'wikidata')

        # 4. Embedding similarity
        candidates = self._embedding_search(entity_type, name, limit=5, min_sim=0.85)
        if candidates:
            # 5. LLM verification
            best = self._llm_verify(entity_type, name, context, candidates)
            if best and best.confidence >= 0.9:
                self._learn_alias(entity_type, best.entity_id, name)
                return MatchResult(True, best.entity_id, best.confidence, 'llm')

        # No match → create new
        new_entity = self._create_entity(entity_type, name, qid)
        return MatchResult(True, new_entity.id, 1.0, 'new')

    # 편의 메서드
    def match_person(self, name, context=None):
        return self.match('person', name, context)

    def match_location(self, name, context=None):
        return self.match('location', name, context)

    def match_event(self, name, context=None):
        return self.match('event', name, context)
```

### 6.6 책 처리 스크립트 (모드 선택)

```python
# poc/scripts/process_book.py

"""
책 처리 통합 스크립트

Usage:
    python process_book.py <book_path> --mode extract   # 추출만 → JSON
    python process_book.py <book_path> --mode match     # 매칭만 → DB
    python process_book.py <book_path> --mode full      # 추출 → 매칭 순차
    python process_book.py <book_path> --mode match --dry-run  # 매칭 리뷰만
"""

import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('book_path', help='책 파일 또는 extraction JSON 경로')
    parser.add_argument('--mode', choices=['extract', 'match', 'full'], default='full')
    parser.add_argument('--dry-run', action='store_true', help='매칭 결과 리뷰만 (DB 반영 안함)')
    parser.add_argument('--output', help='추출 결과 JSON 경로 (extract/full 모드)')
    args = parser.parse_args()

    if args.mode == 'extract':
        # 추출만: 책 → JSON
        result_path = extract_only(args.book_path, args.output)
        print(f"✓ Extracted: {result_path}")

    elif args.mode == 'match':
        # 매칭만: 기존 JSON → DB
        match_only(args.book_path, dry_run=args.dry_run)

    elif args.mode == 'full':
        # 순차: 추출 → 매칭
        result_path = extract_only(args.book_path, args.output)
        print(f"✓ Extracted: {result_path}")
        match_only(result_path, dry_run=args.dry_run)


def extract_only(book_path: str, output_path: str = None) -> str:
    """
    책에서 엔티티 추출 → JSON 저장
    (기존 8200 포트 추출 로직 활용)
    """
    # TODO: 기존 추출 로직 연동
    extracted = extract_entities_from_book(book_path)

    if not output_path:
        output_path = Path(book_path).stem + "_extracted.json"

    save_json(extracted, output_path)
    return output_path


def match_only(json_path: str, dry_run: bool = False):
    """
    추출된 JSON → EntityMatcher → DB
    """
    extracted = load_json(json_path)
    matcher = EntityMatcher(session, embedding_service, wikidata_client)

    results = {'matched': [], 'new': [], 'merged': []}

    for entity_type in ['persons', 'locations', 'events']:
        for entity in extracted.get(entity_type, []):
            result = matcher.match(
                entity_type.rstrip('s'),
                entity['name'],
                context=entity.get('context')
            )
            # ... (이전 로직과 동일)

    print_review(results)

    if not dry_run:
        commit_results(results)
        print(f"✓ Committed: {len(results['matched'])} matched, {len(results['new'])} new")
```

### 6.7 모드별 사용 시나리오

```bash
# 시나리오 1: 추출만 하고 나중에 매칭
python process_book.py book1.txt --mode extract
python process_book.py book2.txt --mode extract
# ... 나중에 ...
python process_book.py book1_extracted.json --mode match

# 시나리오 2: 한번에 다
python process_book.py book1.txt --mode full

# 시나리오 3: 매칭 전 리뷰
python process_book.py book1_extracted.json --mode match --dry-run
# 결과 확인 후
python process_book.py book1_extracted.json --mode match
```

---

## 7. 8200 서버 확장 (Book Extractor 통합)

### 7.1 개요

기존 `tools/book_extractor/server.py` (8200 포트)에 매칭 기능 추가.
새 책 → 8200에 넣기만 하면 추출 → 매칭 → DB 반영까지 처리.

### 7.2 기존 API (추출)

```
/api/books              책 목록
/api/extract/*          추출 시작/취소/상태
/api/queue/*            큐 관리
/api/results/*          추출 결과 (JSON)
/api/zim/*              ZIM 파일 접근
/api/models             모델 선택
/api/speed              속도 모드
```

### 7.3 추가 API (매칭)

```python
# tools/book_extractor/server.py 에 추가

# ─── 매칭 API ───────────────────────────────────────────

@app.post("/api/match/start/{book_id}")
async def start_matching(book_id: str, background_tasks: BackgroundTasks):
    """
    추출 완료된 책의 매칭 시작
    - EntityMatcher로 DB 매칭
    - 결과를 match_results에 저장
    """

@app.get("/api/match/status/{book_id}")
async def get_match_status(book_id: str):
    """매칭 진행률"""

@app.get("/api/match/results/{book_id}")
async def get_match_results(book_id: str):
    """
    매칭 결과 조회 (리뷰용)
    Returns:
        {
            "matched": [...],   # 기존 엔티티와 매칭됨
            "new": [...],       # 신규 생성 예정
            "merged": [...]     # QID 중복 병합됨
        }
    """

@app.post("/api/match/confirm/{book_id}")
async def confirm_matches(book_id: str, decisions: MatchDecisions):
    """
    매칭 확정
    - accept: alias 저장 + source 연결
    - reject: 스킵
    - create: 새 엔티티 생성
    """

# ─── 중복 현황 API ──────────────────────────────────────

@app.get("/api/duplicates/status")
async def get_duplicate_status():
    """
    DB 중복 현황
    Returns:
        {
            "total_duplicates": 10372,
            "merged": 2127,
            "remaining": 8245,
            "recent_merges": [...]
        }
    """

# ─── 자동화 옵션 ────────────────────────────────────────

@app.post("/api/queue/settings")
async def update_queue_settings(settings: QueueSettings):
    """
    큐 설정 변경
    - auto_match: bool  # 추출 완료 후 자동 매칭 시작
    - auto_confirm_threshold: float  # 이 confidence 이상이면 자동 확정 (0.95)
    """
```

### 7.4 UI 확장 (8200 프론트)

기존 HTML에 매칭 탭 추가:

```
┌─────────────────────────────────────────────────────────────┐
│  📚 Book Extractor                                          │
│  [Queue] [Books] [Results] [Matching ✨] [Duplicates ✨]    │
├─────────────────────────────────────────────────────────────┤
```

#### Matching 탭

```
┌─────────────────────────────────────────────────────────────┐
│  📖 Le Morte d'Arthur - Entity Matching                     │
│                                                             │
│  Status: ✅ Extracted → 🔄 Matching...                      │
│                                                             │
│  [Persons ▼] [Locations] [Events]                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ── MATCHED (42) ─────────────────────────────────────     │
│  ┌───────────────────────────────────────────────────┐     │
│  │ "King Arthur" → Arthur, King (id=156)             │     │
│  │ Method: exact | Confidence: 1.0                   │     │
│  │ [✓] [✗]                                           │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
│  ── NEW (8) ───────────────────────────────────────────    │
│  ┌───────────────────────────────────────────────────┐     │
│  │ "Sir Bedivere" → 신규 생성                        │     │
│  │ Wikidata: Q786382                                 │     │
│  │ [Create] [Link] [Skip]                            │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [Auto-confirm high confidence] [Confirm All] [Skip All]   │
└─────────────────────────────────────────────────────────────┘
```

#### Duplicates 탭

```
┌─────────────────────────────────────────────────────────────┐
│  🔄 Duplicate Status                                        │
│                                                             │
│  Before: 10,372 │ Merged: 2,127 │ Remaining: 8,245         │
│  ████████████████░░░░░░░░ 20%                              │
│                                                             │
│  Recent Merges:                                            │
│  • Napoleon: 23 → 1                                        │
│  • Shakespeare: 13 → 1                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.5 워크플로우

```
[새 책 추가]
     │
     ▼
┌─────────────┐
│ 8200 서버   │
│ Queue 탭    │──→ [Start Queue]
└─────────────┘
     │
     ▼ 추출 완료
┌─────────────┐
│ Matching 탭 │──→ [Start Matching] 또는 auto_match=true
└─────────────┘
     │
     ▼ 매칭 완료
┌─────────────┐
│ 리뷰 & 확정 │──→ [Confirm] 또는 auto_confirm (0.95+)
└─────────────┘
     │
     ▼
[DB 반영 + Alias 저장]
```

---

## 8. 실행 계획

| Phase | 작업 | 비고 |
|-------|------|------|
| **1** | entity_aliases 테이블 생성 | DB 마이그레이션 |
| **2** | EntityMatcher 서비스 구현 | `tools/book_extractor/` 내부 |
| **3** | 8200 서버 API 추가 | `/api/match/*`, `/api/duplicates/*` |
| **4** | 8200 UI 확장 | Matching 탭, Duplicates 탭 |
| **5** | 첫 번째 책 처리 | 추출 → 매칭 → 확정 |
| **6** | 반복 | 점진적 품질 개선 |

→ **QID 중복 병합은 책 처리 중 자동으로 발생** (별도 Phase 불필요)

---

## 9. 성공 지표

| 지표 | 현재 | 목표 |
|------|------|------|
| 중복 QID 레코드 | 10,372 | 0 |
| Alias 커버리지 | 0% | 90%+ |
| 신규 매칭 정확도 | - | 95%+ |
| LLM 호출 비율 | - | <20% |

---

## 10. 구현 파일

```
# DB 마이그레이션
backend/alembic/versions/xxx_add_entity_aliases.py

# 8200 서버 확장 (tools/book_extractor/)
tools/book_extractor/
├── server.py                   # 기존 + 매칭 API 추가
├── entity_matcher.py           # EntityMatcher 서비스 (신규)
├── wikidata_client.py          # Wikidata API (신규)
├── llm_verifier.py             # LLM 검증 (신규)
└── static/
    └── index.html              # 기존 UI + Matching/Duplicates 탭

# 모델 (메인 백엔드에서 import)
backend/app/models/entity_alias.py
```

---

## 11. 폐기 문서

다음 문서는 이 문서로 대체되어 삭제됨:
- ~~`docs/planning/ENTITY_NORMALIZATION.md`~~ (삭제됨)
- ~~`docs/planning/v2/ENTITY_MATCHING_STRATEGY.md`~~ (삭제됨)
