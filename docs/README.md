# CHALDEAS Documentation

> 역사 지식 시스템 - 저장고(Storage)에서 도서관(Library)으로

---

## 핵심 개념

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHALDEAS 데이터 흐름                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [원본 텍스트] → [저장고] → [도서관] → [사용자]                  │
│                                                                 │
│  저장고 (Ingestion)        도서관 (Query/Curator)               │
│  • 기계적 분류              • 새 텍스트 생성                     │
│  • 엔티티 추출              • Chain, Article 작성               │
│  • 관계 연결                • 유저 질문 캐싱                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 문서 구조

```
docs/
├── README.md              # 이 파일 (메인 인덱스)
│
├── architecture/          # 시스템 설계
│   ├── V1_ARCHITECTURE.md # ⭐ 핵심 - 저장고/도서관 아키텍처
│   ├── V1_PIPELINE.md     # 텍스트 처리 파이프라인
│   └── CORE_SYSTEMS.md    # SHEBA, LOGOS 등 서브시스템
│
├── concepts/              # 핵심 컨셉
│   ├── HISTORICAL_CHAIN_CONCEPT.md  # 역사의 고리 4가지 유형
│   ├── METHODOLOGY.md     # Braudel, CIDOC-CRM 학술 배경
│   └── SYSTEM_OVERVIEW.md # 전체 시스템 개요
│
├── reference/             # 참조 문서
│   ├── API.md             # REST API 명세
│   ├── DATABASE.md        # DB 스키마
│   ├── MODELS.md          # AI 모델 목록
│   └── PORTS.md           # 포트 설정
│
├── guides/                # 가이드
│   ├── SETUP.md           # 개발 환경 설정
│   ├── DEPLOYMENT.md      # GCP 배포 가이드
│   └── DATA_SYNC_GUIDE.md # 데이터 동기화
│
├── roadmap/               # 로드맵
│   ├── V1_WORKPLAN.md     # V1 작업 계획
│   ├── COST_ESTIMATION.md # AI 비용 산정
│   └── V1_WORKLOG.md      # 작업 로그
│
├── data/                  # 데이터 관련
│   ├── DATA_SOURCES.md    # 데이터 소스 목록
│   ├── DATA_COLLECTION.md # 수집 방법
│   └── LOCATION_RESOLUTION.md  # 위치 해상도
│
└── archive/               # 아카이브 (V0, 참고용)
    ├── REDESIGN_PLAN.md   # V0 → V1 전환 계획
    └── ...
```

---

## 읽기 순서

### 1단계: 핵심 이해
| 순서 | 문서 | 설명 |
|------|------|------|
| 1 | [V1_ARCHITECTURE.md](./architecture/V1_ARCHITECTURE.md) | **필독** - 저장고/도서관 분리, 큐레이터 시스템 |
| 2 | [HISTORICAL_CHAIN_CONCEPT.md](./concepts/HISTORICAL_CHAIN_CONCEPT.md) | 4가지 체인 유형 (인물/장소/시대/인과) |
| 3 | [SYSTEM_OVERVIEW.md](./concepts/SYSTEM_OVERVIEW.md) | 사용자 경험, 충돌 처리 |

### 2단계: 상세 설계
| 문서 | 설명 |
|------|------|
| [V1_PIPELINE.md](./architecture/V1_PIPELINE.md) | NER, 체인 생성 파이프라인 |
| [METHODOLOGY.md](./concepts/METHODOLOGY.md) | Braudel 시간 스케일, CIDOC-CRM |
| [DATABASE.md](./reference/DATABASE.md) | 테이블 스키마 |

### 3단계: 실행
| 문서 | 설명 |
|------|------|
| [V1_WORKPLAN.md](./roadmap/V1_WORKPLAN.md) | 체크포인트별 작업 계획 |
| [COST_ESTIMATION.md](./roadmap/COST_ESTIMATION.md) | AI 호출 비용 |
| [SETUP.md](./guides/SETUP.md) | 개발 환경 설정 |

---

## 빠른 시작

\`\`\`bash
# 환경 변수 설정
cp .env.example .env

# Docker로 실행
docker-compose up -d

# 접속
# Frontend: http://localhost:5200
# Backend API: http://localhost:8100/docs
\`\`\`

---

## 핵심 시스템

| 시스템 | 역할 | 레이어 |
|--------|------|--------|
| **CHALDEAS** | 세계 상태 (불변 스냅샷) | 저장고 |
| **SHEBA** | 질의 파싱, 벡터 검색 | 도서관 |
| **LOGOS** | LLM 기반 응답 생성 | 도서관 |
| **PAPERMOON** | 사실 검증 | 도서관 |
| **LAPLACE** | 출처 연결, 설명 | 도서관 |
| **Curator** | Chain/Article 생성 | 도서관 |

---

## 기술 스택

- **Frontend**: React 18 + TypeScript + react-globe.gl + Zustand
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0
- **Database**: PostgreSQL 16 + pgvector
- **AI**: Ollama (Qwen3 8B) + OpenAI (GPT-5.1)
- **Deploy**: Docker Compose / GCP Cloud Run
