# CHALDEAS Documentation

> "전체를 보는 구조, 질문에 맞게 픽업해서 설명해주는 AI"

## 문서 구조

```
docs/
├── README.md                    # 이 파일 (문서 목차)
│
├── 배포 & 운영 가이드
│   ├── CLOUD_OVERVIEW.md        # 클라우드 배포 개요
│   ├── DEPLOYMENT.md            # 상세 배포 가이드 (GCP)
│   ├── COST_ANALYSIS.md         # 비용 분석
│   └── KNOWLEDGE_SHARING.md     # 지식 공유 가이드
│
├── implemented/                 # 구현 완료된 기능 문서
│   ├── ARCHITECTURE.md          # 시스템 아키텍처
│   ├── DATABASE.md              # 데이터베이스 스키마
│   ├── API.md                   # API 명세
│   └── CORE_SYSTEMS.md          # Core 시스템 (SHEBA, LAPLACE 등)
│
├── planning/                    # 기획 중인 기능 문서
│   ├── AI_PIPELINE.md           # AI 파이프라인 상세 기획
│   ├── DATA_SOURCES.md          # 외부 데이터 소스 연동 계획
│   └── FUTURE_FEATURES.md       # 향후 기능 로드맵
│
└── guides/                      # 가이드 문서
    ├── SETUP.md                 # 개발 환경 설정
    ├── CONTRIBUTING.md          # 기여 가이드
    └── DATA_FORMAT.md           # 데이터 형식 가이드
```

---

## 배포 & 운영 가이드

| 문서 | 설명 |
|------|------|
| [CLOUD_OVERVIEW.md](./CLOUD_OVERVIEW.md) | 클라우드 배포 옵션 비교, 아키텍처 개요 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Google Cloud Run 배포 상세 가이드 |
| [COST_ANALYSIS.md](./COST_ANALYSIS.md) | 서비스별 비용 분석, 최적화 전략 |
| [KNOWLEDGE_SHARING.md](./KNOWLEDGE_SHARING.md) | 기술 지식 공유 방법 가이드 |

---

## 프로젝트 개요

CHALDEAS는 Fate/Grand Order의 칼데아 시스템에서 영감받은
역사/철학/과학사/신화/인물사 통합 탐색 플랫폼입니다.

### 핵심 시스템

| 시스템 | 역할 | 상태 |
|--------|------|------|
| **CHALDEAS** | 세계 상태 관리 (불변 스냅샷) | 구현됨 |
| **SHEBA** | 관측 및 질의 처리 | 구현됨 |
| **LAPLACE** | 설명 및 출처 연결 | 구현됨 |
| **TRISMEGISTUS** | 시스템 조율 | 구현됨 |
| **PAPERMOON** | 제안 검증 | 구현됨 |
| **LOGOS** | LLM 기반 제안자 | 구현됨 |
| **ANIMA** | 학습 시스템 | 계획 중 |

### 기술 스택

- **Frontend**: React + TypeScript + react-globe.gl
- **Backend**: Python + FastAPI
- **Database**: PostgreSQL
- **AI**: LangChain (OpenAI/Anthropic)
- **Deploy**: Docker Compose

## 빠른 시작

```bash
# 환경 변수 설정
cp .env.example .env

# Docker로 실행
docker-compose up -d

# 접속
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000/docs
```
