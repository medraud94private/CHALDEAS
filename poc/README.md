# CHALDEAS V1 PoC

Historical Chain 개념증명 (Proof of Concept)

## 개요

이 PoC는 "역사의 고리" (HistoricalChain) 시스템의 핵심 개념을 검증합니다:

- **4가지 큐레이션 유형**: person_story, place_story, era_story, causal_chain
- **Braudel의 시간 구조**: événementielle, conjuncture, longue durée
- **하이브리드 NER**: spaCy + GPT 검증
- **캐싱 및 승격 시스템**: user → cached → featured → system

## 설치

```bash
cd poc

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# spaCy 모델 다운로드
python -m spacy download en_core_web_sm
```

## 환경 설정

`.env` 파일 생성:

```env
OPENAI_API_KEY=sk-...  # 선택사항: LLM 검증용
DEBUG=true
```

## 실행

### 1. 데이터베이스 시드

```bash
python scripts/seed_db.py
```

### 2. 서버 시작

```bash
uvicorn app.main:app --reload --port 8200
```

### 3. API 테스트

- Swagger UI: http://localhost:8200/docs
- Health Check: http://localhost:8200/health

## API 엔드포인트

### 체인 (Chains)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/v1/chains` | GET | 체인 목록 조회 |
| `/api/v1/chains/{id}` | GET | 특정 체인 조회 |
| `/api/v1/chains/curate` | POST | 큐레이션 요청 |
| `/api/v1/chains` | POST | 수동 체인 생성 |

### 엔티티 (Entities)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/v1/entities/persons` | GET | 인물 목록 |
| `/api/v1/entities/locations` | GET | 장소 목록 |
| `/api/v1/entities/events` | GET | 사건 목록 |
| `/api/v1/entities/periods` | GET | 시대 목록 |

### 큐레이션 요청 예시

```json
POST /api/v1/chains/curate
{
  "chain_type": "person_story",
  "person_id": 1,
  "max_segments": 10,
  "language": "en"
}
```

## NER 파이프라인 테스트

```bash
# 기본 테스트 (spaCy만)
python scripts/test_ner.py

# LLM 검증 포함
python scripts/test_ner.py --llm
```

## 디렉토리 구조

```
poc/
├── app/
│   ├── api/           # API 라우터
│   ├── core/          # 핵심 로직
│   │   └── extraction/  # NER 파이프라인
│   ├── models/        # SQLAlchemy 모델
│   ├── schemas/       # Pydantic 스키마
│   ├── services/      # 비즈니스 로직
│   ├── config.py
│   ├── database.py
│   └── main.py
├── data/
│   └── seeds/         # 샘플 데이터
├── scripts/           # 유틸리티 스크립트
├── tests/             # 테스트
└── requirements.txt
```

## 다음 단계

1. PoC 검증 후 본 backend로 마이그레이션
2. 벡터 검색 통합 (pgvector)
3. 프론트엔드 시각화 컴포넌트
