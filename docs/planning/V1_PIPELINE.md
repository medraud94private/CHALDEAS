# CHALDEAS V1 텍스트 처리 파이프라인

## 개요

새로운 텍스트가 입력되면 다음 순서로 처리됩니다:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Raw Text   │────▶│  NER 추출   │────▶│  엔티티 연결 │────▶│  체인 생성  │
│  (입력)     │     │  (spaCy+LLM)│     │  (DB 매칭)  │     │  (큐레이션) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 1단계: 텍스트 입력

### 지원 소스
| 소스 | 설명 | 예시 |
|------|------|------|
| Gutenberg | 영문 고전 | 플라톤의 대화편, 로마사 |
| CText | 중국 고전 | 논어, 사기 |
| Perseus | 그리스/로마 원전 | 일리아드, 역사 |
| 사용자 입력 | 직접 입력 텍스트 | 위키피디아 발췌 등 |

### 입력 형식
```python
# TextSource 모델
{
    "source_type": "gutenberg",      # 소스 유형
    "external_id": "PG1234",         # 원본 ID
    "title": "The Republic",
    "author": "Plato",
    "content": "...",                 # 전체 텍스트
    "language": "en"
}
```

---

## 2단계: NER (Named Entity Recognition)

### 하이브리드 파이프라인

```
┌──────────────────────────────────────────────────────────────┐
│                    HybridNERPipeline                         │
├──────────────────────────────────────────────────────────────┤
│  Step 1: spaCy (무료, 빠름)                                   │
│  ├── 모델: en_core_web_lg                                    │
│  ├── 추출: PERSON, GPE, LOC, DATE, EVENT                     │
│  └── 결과: 후보 엔티티 목록 (confidence: 0.7)                  │
│                                                              │
│  Step 2: LLM 검증 (무료 로컬 or 유료 클라우드)                  │
│  ├── Ollama (기본): qwen3:8b - 무료, 로컬                     │
│  ├── OpenAI (폴백): gpt-5-nano - 유료, 빠름                   │
│  └── 작업: 오분류 수정, 정규화, 신뢰도 조정                     │
└──────────────────────────────────────────────────────────────┘
```

### 처리 예시

**입력 텍스트:**
```
Socrates was a classical Greek philosopher credited as the founder of Western philosophy.
He was born in Athens around 470 BCE and died in 399 BCE.
```

**Step 1 - spaCy 결과:**
```json
[
  {"text": "Socrates", "type": "person", "confidence": 0.7},
  {"text": "Greek", "type": "location", "confidence": 0.7},
  {"text": "Athens", "type": "location", "confidence": 0.7},
  {"text": "470 BCE", "type": "location", "confidence": 0.7},  // 오류!
  {"text": "399 BCE", "type": "location", "confidence": 0.7}   // 오류!
]
```

**Step 2 - Ollama 검증 후:**
```json
[
  {"text": "Socrates", "type": "person", "normalized": "Socrates", "confidence": 0.95},
  {"text": "Greek", "type": "location", "normalized": "Ancient Greece", "confidence": 0.85},
  {"text": "Athens", "type": "location", "normalized": "Athens", "confidence": 0.95},
  {"text": "470 BCE", "type": "time", "normalized": "-470", "confidence": 0.90},  // 수정됨
  {"text": "399 BCE", "type": "time", "normalized": "-399", "confidence": 0.90}   // 수정됨
]
```

### 코드 위치
```
poc/app/core/extraction/ner_pipeline.py
├── HybridNERPipeline        # 메인 클래스
├── _call_ollama()           # 로컬 LLM 호출
├── _call_openai()           # 클라우드 LLM 폴백
└── _verify_with_llm()       # 검증 프롬프트 실행
```

---

## 3단계: 엔티티 연결 (Entity Linking)

### 프로세스

```
추출된 엔티티 ──▶ DB 검색 ──▶ 매칭 or 신규 생성
     │                           │
     │  "Socrates"               │
     │      │                    │
     │      ▼                    ▼
     │  persons 테이블 검색    ID: 1 (기존)
     │                       or
     │                       ID: 6 (신규 생성)
```

### 매칭 전략
1. **정확 매칭**: `name = 'Socrates'`
2. **유사 매칭**: `name ILIKE '%socrat%'`
3. **벡터 검색**: 임베딩 유사도 (향후)
4. **신규 생성**: 매칭 실패 시 새 엔티티 생성

### TextMention 저장
```python
# 텍스트 내 언급 기록
{
    "text_source_id": 1,
    "chunk_start": 0,
    "chunk_end": 8,
    "entity_type": "person",
    "entity_id": 1,               # persons.id = 1 (Socrates)
    "entity_text": "Socrates",
    "normalized_text": "Socrates",
    "confidence": 0.95,
    "extraction_model": "ollama-verified",
    "quote": "Socrates was a classical Greek philosopher..."
}
```

---

## 4단계: 체인 생성 (Curation)

### 4가지 체인 유형

| 유형 | 설명 | 예시 |
|------|------|------|
| **person_story** | 인물의 생애 | "소크라테스의 이야기" |
| **place_story** | 장소의 역사 | "아테네의 역사" |
| **era_story** | 시대 개관 | "고전 그리스 시대" |
| **causal_chain** | 인과관계 흐름 | "펠로폰네소스 전쟁의 연쇄" |

### 생성 프로세스

```
┌─────────────────────────────────────────────────────────────┐
│  CurationRequest                                            │
│  {                                                          │
│    "chain_type": "person_story",                            │
│    "person_id": 1,          // Socrates                     │
│    "max_segments": 5                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  ChainGenerator                                             │
│  1. 캐시 확인 (기존 체인 있으면 반환)                          │
│  2. 관련 이벤트 조회                                         │
│  3. 각 이벤트에 대해 narrative 생성 (Ollama/OpenAI)          │
│  4. 체인 저장 및 반환                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  HistoricalChain                                            │
│  {                                                          │
│    "title": "The Story of Socrates",                        │
│    "chain_type": "person_story",                            │
│    "segments": [                                            │
│      {                                                      │
│        "segment_order": 1,                                  │
│        "event_id": 3,                                       │
│        "narrative": "The Battle of Marathon (490 BCE)..."   │
│      },                                                     │
│      {                                                      │
│        "segment_order": 2,                                  │
│        "event_id": 1,                                       │
│        "narrative": "Socrates was tried and executed..."    │
│      }                                                      │
│    ]                                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### Narrative 생성 (LLM)

```python
prompt = """Write a brief (2-3 sentences) narrative about this historical event.
Focus on its significance and connections. Be concise and factual.

Event: Trial and Death of Socrates (-399)
Description: Socrates was sentenced to death by drinking hemlock
Person: Socrates

Narrative:"""

# Ollama 응답 (약 30-90초)
"Socrates was tried and executed in 399 BCE for impiety and
corrupting Athens' youth, reflecting the city's political tensions.
His death became a symbol of intellectual integrity and profoundly
influenced Western philosophy through his students like Plato."
```

### 코드 위치
```
poc/app/services/chain_generator.py
├── ChainGenerator               # 메인 클래스
├── generate_chain()             # 체인 생성 진입점
├── _generate_person_story()     # 인물 체인
├── _generate_place_story()      # 장소 체인
├── _generate_era_story()        # 시대 체인
├── _generate_causal_chain()     # 인과 체인
├── _generate_narrative()        # LLM narrative 생성
└── _call_ollama()               # Ollama API 호출
```

---

## 5단계: 캐싱 및 승격

### 승격 시스템

```
user (첫 생성)
    │
    │ 5회 조회
    ▼
cached (캐시됨)
    │
    │ 50회 조회
    ▼
featured (추천)
    │
    │ 200회 조회
    ▼
system (영구 보존)
```

### 캐시 동작
- **첫 요청**: 새 체인 생성 (약 4-5분)
- **재요청**: 캐시에서 즉시 반환 (<1초)
- **자주 조회되는 체인**: 자동으로 승격

---

## 전체 데이터 흐름

```
                     ┌─────────────────────────────────────────┐
                     │           CHALDEAS V1 Pipeline          │
                     └─────────────────────────────────────────┘

┌──────────┐    ┌──────────────────────────────────────────────────────────┐
│ Gutenberg│───▶│                                                          │
│ CText    │    │  TextSource                                              │
│ Perseus  │    │  ├── id: 1                                               │
│ User     │    │  ├── content: "Socrates was a philosopher..."            │
└──────────┘    │  └── language: "en"                                      │
                └──────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────────────┐
                │  NER Pipeline (spaCy + Ollama)                           │
                │  ├── 추출: Socrates(person), Athens(location), -399(time)│
                │  └── 정확도: spaCy 70% → Ollama 검증 후 95%               │
                └──────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────────────┐
                │  Entity Linking                                          │
                │  ├── Socrates → persons.id = 1                           │
                │  ├── Athens → locations.id = 1                           │
                │  └── -399 → events.date_start = -399                     │
                └──────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────────────┐
                │  TextMention (텍스트-엔티티 연결 저장)                     │
                │  ├── text_source_id: 1                                   │
                │  ├── entity_type: "person"                               │
                │  ├── entity_id: 1 (Socrates)                             │
                │  └── quote: "Socrates was a philosopher..."              │
                └──────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────────────┐
                │  Chain Generation (사용자 요청 시)                        │
                │  ├── 요청: "소크라테스의 이야기"                           │
                │  ├── 관련 이벤트 조회                                     │
                │  ├── Ollama로 narrative 생성                             │
                │  └── HistoricalChain 반환                                │
                └──────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────────────┐
                │  Frontend Display                                        │
                │  ├── 체인 제목: "The Story of Socrates"                   │
                │  ├── 세그먼트 1: Marathon 전투 narrative                  │
                │  ├── 세그먼트 2: 재판과 처형 narrative                     │
                │  └── 세그먼트 3: 플라톤 아카데미 설립 narrative             │
                └──────────────────────────────────────────────────────────┘
```

---

## PoC 파일 구조

```
poc/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── config.py                  # 설정 (Ollama/OpenAI)
│   ├── database.py                # SQLite 비동기 설정
│   │
│   ├── models/                    # SQLAlchemy 모델
│   │   ├── person.py
│   │   ├── location.py
│   │   ├── event.py
│   │   ├── period.py
│   │   ├── chain.py               # HistoricalChain, ChainSegment
│   │   └── text_mention.py        # TextSource, TextMention
│   │
│   ├── schemas/                   # Pydantic 스키마
│   │   └── chain.py               # CurationRequest/Response
│   │
│   ├── api/                       # API 엔드포인트
│   │   ├── chains.py              # /curate, CRUD
│   │   └── entities.py            # persons, locations, periods
│   │
│   ├── services/
│   │   └── chain_generator.py     # 체인 생성 로직
│   │
│   └── core/
│       └── extraction/
│           └── ner_pipeline.py    # 하이브리드 NER
│
├── scripts/
│   ├── seed_db.py                 # 샘플 데이터 시딩
│   ├── test_ner.py                # NER 테스트
│   ├── test_ollama.py             # Ollama 연결 테스트
│   └── test_curate.py             # 체인 생성 테스트
│
├── static/
│   └── index.html                 # 테스트 웹 UI
│
└── data/
    ├── seeds/sample_data.json     # 샘플 역사 데이터
    └── chaldeas_poc.db            # SQLite DB 파일
```

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/` | 테스트 페이지 (index.html) |
| GET | `/health` | 서버 상태 확인 |
| GET | `/api/v1/entities/persons` | 인물 목록 |
| GET | `/api/v1/entities/locations` | 장소 목록 |
| GET | `/api/v1/entities/periods` | 시대 목록 |
| GET | `/api/v1/entities/events` | 이벤트 목록 |
| POST | `/api/v1/chains/curate` | **체인 생성/조회** |
| GET | `/api/v1/chains` | 체인 목록 |
| GET | `/api/v1/chains/{id}` | 체인 상세 |

---

## 실행 방법

```bash
# 1. PoC 디렉토리로 이동
cd poc

# 2. 의존성 설치
pip install -r requirements.txt

# 3. spaCy 모델 다운로드
python -m spacy download en_core_web_lg

# 4. Ollama 시작 (별도 터미널)
ollama serve

# 5. 데이터베이스 시딩
python scripts/seed_db.py

# 6. 서버 시작
uvicorn app.main:app --port 8200

# 7. 브라우저에서 접속
# http://localhost:8200
```

---

## 성능 지표

| 작업 | 소요 시간 | 비용 |
|------|----------|------|
| NER (spaCy) | <1초 | 무료 |
| NER 검증 (Ollama) | 10-30초 | 무료 |
| Narrative 생성 (Ollama) | 60-90초/세그먼트 | 무료 |
| 체인 생성 (3 세그먼트) | 약 4-5분 | 무료 |
| 캐시된 체인 조회 | <1초 | 무료 |

---

## 향후 개선 사항

1. **속도 개선**: 더 작은 모델 (qwen3:4b) 또는 OpenAI 사용
2. **벡터 검색**: 엔티티 연결에 임베딩 유사도 활용
3. **배치 처리**: 대량 텍스트 일괄 처리
4. **본 백엔드 통합**: PoC 검증 후 backend/에 통합
