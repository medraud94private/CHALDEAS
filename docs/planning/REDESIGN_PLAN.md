# CHALDEAS V2 재설계 계획

> ⚠️ **ARCHIVED**: 이 문서는 [V1_ARCHITECTURE.md](./V1_ARCHITECTURE.md)로 대체되었습니다.
> 아래 내용은 초기 계획으로, 참고용으로만 사용하세요.

---

## 개요

기존 구조를 레거시로 유지하면서 새로운 Historical Chain 기반 아키텍처를 병행 개발합니다.

---

## 전환 전략

### 1. 레거시 유지

```
현재 서버 (운영):
  backend/app/models/event.py      ← 기존 구조 유지
  backend/app/models/person.py     ← 기존 구조 유지
  backend/app/models/location.py   ← 기존 구조 유지
```

### 2. 신규 개발 (별도 모듈)

```
신규 개발:
  backend/app/models/v2/           ← 새 모델들
  backend/app/api/v2/              ← 새 API
  backend/app/core/chain/          ← Historical Chain 로직
```

### 3. 전환 시점

- **완성 기준**: V2 API가 기존 기능 100% 커버 + 새 기능
- **전환 방식**:
  1. V2 API 병행 운영
  2. 프론트엔드 점진적 전환
  3. V1 API 폐기 (3개월 유예)

---

## 결정 사항 요약

| 항목 | 결정 | 근거 |
|-----|------|------|
| Period/Era 구축 | 하이브리드 | 기본 틀 수동 + 세부 AI |
| Location 계층 | 이중 관리 | modern + historical |
| HistoricalChain | 캐싱 + 승격 | user → cached → featured → system |
| NER 방식 | 하이브리드 | spaCy + GPT-5-nano (fallback: GPT-5.1) |

---

## Phase 1: 데이터 모델 확장

### 1.1 Period 테이블

**파일**: `backend/app/models/v2/period.py`

```python
class Period(Base, TimestampMixin):
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    name_ko = Column(String(200))
    slug = Column(String(200), unique=True, index=True)
    year_start = Column(Integer, nullable=False)  # BCE는 음수
    year_end = Column(Integer)
    scale = Column(String(20))  # evenementielle, conjuncture, longue_duree
    parent_id = Column(Integer, ForeignKey("periods.id"))
    description = Column(Text)
    description_ko = Column(Text)
    is_manual = Column(Boolean, default=True)
```

### 1.2 Location 확장

**파일**: `backend/app/models/location.py` (기존 파일 확장)

```python
# 추가 필드
modern_parent_id = Column(Integer, ForeignKey("locations.id"))
historical_parent_id = Column(Integer, ForeignKey("locations.id"))
hierarchy_level = Column(String(30))  # site, city, region, country, continent
valid_from = Column(Integer)   # 역사적 유효 시작 연도
valid_until = Column(Integer)  # 역사적 유효 종료 연도
```

### 1.3 Event 확장

**파일**: `backend/app/models/event.py` (기존 파일 확장)

```python
# 추가 필드
temporal_scale = Column(String(20))  # evenementielle, conjuncture, longue_duree
period_id = Column(Integer, ForeignKey("periods.id"))
certainty = Column(String(20))  # fact, probable, legendary, mythological
```

---

## Phase 2: HistoricalChain 시스템

### 2.1 모델

**파일**: `backend/app/models/v2/chain.py`

```python
class HistoricalChain(Base, TimestampMixin):
    __tablename__ = "historical_chains"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    title_ko = Column(String(500))
    description = Column(Text)
    chain_type = Column(String(30))  # person_story, place_story, era_story, causal_chain

    person_id = Column(Integer, ForeignKey("persons.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    period_id = Column(Integer, ForeignKey("periods.id"))

    visibility = Column(String(20), default="user")  # user, cached, featured, system
    access_count = Column(Integer, default=0)
    created_by_master_id = Column(Integer, ForeignKey("masters.id"))
    promoted_at = Column(DateTime)


class ChainSegment(Base):
    __tablename__ = "chain_segments"

    id = Column(Integer, primary_key=True)
    chain_id = Column(Integer, ForeignKey("historical_chains.id", ondelete="CASCADE"))
    segment_order = Column(Integer, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"))
    narrative = Column(Text)
    narrative_ko = Column(Text)
    connection_type = Column(String(30))  # causes, follows, part_of, leads_to
```

### 2.2 승격 서비스

**파일**: `backend/app/services/chain_service.py`

```python
PROMOTION_THRESHOLDS = {
    'user': 0,
    'cached': 5,
    'featured': 50,
    'system': 200
}

VISIBILITY_ORDER = ['user', 'cached', 'featured', 'system']

async def increment_access_and_promote(chain_id: int, db: AsyncSession):
    chain = await db.get(HistoricalChain, chain_id)
    chain.access_count += 1

    current_idx = VISIBILITY_ORDER.index(chain.visibility)
    for i in range(current_idx + 1, len(VISIBILITY_ORDER)):
        next_level = VISIBILITY_ORDER[i]
        if chain.access_count >= PROMOTION_THRESHOLDS[next_level]:
            chain.visibility = next_level
            chain.promoted_at = datetime.utcnow()
        else:
            break

    await db.commit()
```

---

## Phase 3: 텍스트-엔티티 연결

### 3.1 모델

**파일**: `backend/app/models/v2/text_mention.py`

```python
class TextSource(Base, TimestampMixin):
    __tablename__ = "text_sources"

    id = Column(Integer, primary_key=True)
    source_type = Column(String(50), nullable=False)  # gutenberg, ctext, perseus
    external_id = Column(String(100))
    title = Column(String(500))
    author = Column(String(200))
    content = Column(Text)
    language = Column(String(10))
    processed = Column(Boolean, default=False)


class TextMention(Base, TimestampMixin):
    __tablename__ = "text_mentions"

    id = Column(Integer, primary_key=True)
    text_source_id = Column(Integer, ForeignKey("text_sources.id", ondelete="CASCADE"))
    chunk_start = Column(Integer)
    chunk_end = Column(Integer)
    entity_type = Column(String(20))  # person, location, event, time
    entity_id = Column(Integer)
    entity_text = Column(String(500))
    normalized_text = Column(String(500))
    confidence = Column(Numeric(3, 2))
    extraction_model = Column(String(50))
    quote = Column(Text)
```

### 3.2 하이브리드 NER

**파일**: `backend/app/core/extraction/ner_pipeline.py`

```python
class HybridNERPipeline:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_lg")
        self.client = OpenAI()
        self.primary_model = "gpt-5-nano"
        self.fallback_model = "gpt-5.1-chat-latest"

    async def extract(self, text: str, context: dict = None) -> List[Entity]:
        # Step 1: spaCy (무료)
        candidates = self._spacy_extract(text)

        # Step 2: LLM 검증 (유료)
        verified = await self._llm_verify(text, candidates, context)

        return verified
```

---

## Phase 4: 큐레이션 API

### 4.1 엔드포인트

**파일**: `backend/app/api/v2/curation.py`

```python
@router.post("/chain")
async def create_or_get_chain(
    request: CurationRequest,
    db: AsyncSession = Depends(get_db),
    master: Master = Depends(get_current_master)
) -> CurationResponse:
    # 캐시 확인
    existing = await find_similar_chain(db, request)
    if existing:
        await increment_access_and_promote(existing.id, db)
        return existing

    # 새로 생성
    chain = await generate_chain(db, request, master)
    return chain
```

---

## Phase 5: 프론트엔드

### 5.1 컴포넌트 구조

```
frontend/src/components/chain/
  ├── ChainView.tsx           # 메인 뷰
  ├── PersonStoryView.tsx     # 인물 스토리
  ├── PlaceStoryView.tsx      # 장소 스토리
  ├── EraStoryView.tsx        # 시대 스토리
  ├── CausalChainView.tsx     # 인과 체인
  └── ChainTimeline.tsx       # 체인 타임라인 시각화
```

---

## 마이그레이션 순서

```
1. periods 테이블 생성
   └── 초기 데이터 삽입 (고대 그리스, 르네상스 등)

2. locations 테이블 확장
   └── modern_parent_id, historical_parent_id 컬럼 추가

3. events 테이블 확장
   └── temporal_scale, period_id, certainty 컬럼 추가

4. historical_chains, chain_segments 테이블 생성

5. text_sources, text_mentions 테이블 생성
```

---

## 파일 목록

### 신규 생성

| 파일 | 내용 |
|-----|------|
| `backend/app/models/v2/__init__.py` | V2 모델 패키지 |
| `backend/app/models/v2/period.py` | Period 모델 |
| `backend/app/models/v2/chain.py` | HistoricalChain, ChainSegment |
| `backend/app/models/v2/text_mention.py` | TextSource, TextMention |
| `backend/app/services/chain_service.py` | 체인 생성/승격 로직 |
| `backend/app/core/extraction/ner_pipeline.py` | 하이브리드 NER |
| `backend/app/api/v2/curation.py` | 큐레이션 API |
| `backend/app/schemas/v2/chain.py` | Pydantic 스키마 |

### 수정 (확장)

| 파일 | 변경 |
|-----|------|
| `backend/app/models/location.py` | 계층 필드 추가 |
| `backend/app/models/event.py` | temporal_scale, certainty 추가 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|-----|----------|
| 2026-01-01 | 초기 계획 문서 작성 |
