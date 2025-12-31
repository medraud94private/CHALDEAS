# CHALDEAS 클라우드 배포 개요

## 왜 클라우드인가?

로컬 개발 환경에서 프로덕션으로 전환할 때 클라우드를 사용하면:

- **확장성**: 트래픽에 따라 자동 스케일링
- **안정성**: 고가용성, 자동 복구
- **보안**: 관리형 SSL, 시크릿 관리
- **비용 효율**: 사용한 만큼만 지불

---

## 클라우드 옵션 비교

### 1. Google Cloud Platform (GCP)

| 서비스 | 용도 | 특징 |
|--------|------|------|
| **Cloud Run** | 컨테이너 실행 | 서버리스, 자동 스케일링, Docker 지원 |
| **Cloud SQL** | PostgreSQL | 관리형 DB, pgvector 지원 |
| **Cloud Build** | CI/CD | GitHub 연동, 자동 배포 |
| **Secret Manager** | API 키 관리 | 암호화된 시크릿 저장 |

**장점**: 한국 리전 (서울), 무료 티어 넉넉함, Cloud Run 편리함
**단점**: 러닝 커브, 콘솔 UI 복잡

### 2. AWS

| 서비스 | GCP 대응 |
|--------|----------|
| ECS/Fargate | Cloud Run |
| RDS | Cloud SQL |
| CodePipeline | Cloud Build |
| Secrets Manager | Secret Manager |

**장점**: 가장 큰 생태계, 문서 풍부
**단점**: 복잡한 IAM, 비용 예측 어려움

### 3. Azure

| 서비스 | GCP 대응 |
|--------|----------|
| Container Apps | Cloud Run |
| Azure Database | Cloud SQL |
| Azure DevOps | Cloud Build |
| Key Vault | Secret Manager |

**장점**: Microsoft 제품 통합, 엔터프라이즈
**단점**: 문서 분산, 가격 정책 복잡

### 4. 대안: PaaS 서비스

| 서비스 | 특징 | 비용 |
|--------|------|------|
| **Vercel** | Frontend 특화, 자동 배포 | 무료 ~ $20/월 |
| **Railway** | 간단한 배포, DB 포함 | $5 ~ $20/월 |
| **Render** | Heroku 대안, PostgreSQL | $7 ~ $25/월 |
| **Fly.io** | 엣지 배포, 저렴한 가격 | $0 ~ $10/월 |
| **Supabase** | PostgreSQL + Auth + API | 무료 ~ $25/월 |

---

## CHALDEAS 권장 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Production Architecture                       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Google Cloud Platform                 │    │
│  │                                                          │    │
│  │   ┌──────────────┐         ┌──────────────┐             │    │
│  │   │  Cloud Run   │         │  Cloud Run   │             │    │
│  │   │  (Frontend)  │────────→│  (Backend)   │             │    │
│  │   │   nginx      │         │   FastAPI    │             │    │
│  │   │   React SPA  │         │   gunicorn   │             │    │
│  │   └──────────────┘         └──────┬───────┘             │    │
│  │          │                        │                      │    │
│  │          │                        ▼                      │    │
│  │          │                 ┌──────────────┐             │    │
│  │          │                 │  Cloud SQL   │             │    │
│  │          │                 │  PostgreSQL  │             │    │
│  │          │                 │  + pgvector  │             │    │
│  │          │                 └──────────────┘             │    │
│  │          │                        ▲                      │    │
│  │          │                        │                      │    │
│  │          │                 ┌──────────────┐             │    │
│  │          │                 │   Secret     │             │    │
│  │          │                 │   Manager    │             │    │
│  │          │                 │  (API Keys)  │             │    │
│  │          │                 └──────────────┘             │    │
│  │          │                                               │    │
│  │   ┌──────┴───────┐                                      │    │
│  │   │ Cloud CDN    │  (선택사항)                           │    │
│  │   │ Load Balancer│                                      │    │
│  │   └──────────────┘                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    External Services                     │    │
│  │                                                          │    │
│  │   ┌──────────────┐         ┌──────────────┐             │    │
│  │   │   OpenAI     │         │  Anthropic   │             │    │
│  │   │   API        │         │   API        │             │    │
│  │   └──────────────┘         └──────────────┘             │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 데이터 흐름

```
사용자 요청:
┌──────┐    HTTPS     ┌──────────┐    REST API    ┌──────────┐
│ User │ ──────────→  │ Frontend │ ────────────→  │ Backend  │
└──────┘              │ (React)  │                │ (FastAPI)│
                      └──────────┘                └────┬─────┘
                                                       │
                           ┌───────────────────────────┤
                           │                           │
                           ▼                           ▼
                    ┌──────────┐              ┌──────────────┐
                    │ Cloud SQL│              │ OpenAI/      │
                    │ (pgvector)              │ Anthropic API│
                    └──────────┘              └──────────────┘
```

---

## 배포 단계 요약

| 단계 | 설명 | 소요 시간 |
|------|------|-----------|
| 1. GCP 프로젝트 생성 | 프로젝트, 결제 설정 | 10분 |
| 2. API 활성화 | Cloud Run, SQL, Secret Manager | 5분 |
| 3. Cloud SQL 설정 | PostgreSQL + pgvector 인스턴스 | 10분 |
| 4. Secret 설정 | DB URL, API 키 저장 | 5분 |
| 5. 첫 배포 | Backend, Frontend 빌드 및 배포 | 15분 |
| 6. CI/CD 설정 | Cloud Build 트리거 | 10분 |
| **총** | | **약 1시간** |

---

## 다음 단계

1. [DEPLOYMENT.md](./DEPLOYMENT.md) - 상세 배포 가이드
2. [COST_ANALYSIS.md](./COST_ANALYSIS.md) - 비용 분석
3. [KNOWLEDGE_SHARING.md](./KNOWLEDGE_SHARING.md) - 지식 공유 방법
