# CHALDEAS Google Cloud 배포 가이드

## 개요

이 가이드는 CHALDEAS를 Google Cloud Run에 배포하는 방법을 설명합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                    배포 아키텍처                              │
│                                                              │
│    GitHub ──→ Cloud Build ──→ Container Registry            │
│                    │                                         │
│         ┌─────────┴─────────┐                               │
│         ▼                   ▼                                │
│    Cloud Run            Cloud Run                            │
│    (Backend)           (Frontend)                            │
│         │                                                    │
│         ▼                                                    │
│    Cloud SQL (PostgreSQL + pgvector)                         │
│                                                              │
│    Secret Manager (API Keys)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 사전 요구사항

- Google Cloud 계정 및 프로젝트
- `gcloud` CLI 설치 및 인증
- Docker 설치 (로컬 테스트용)

---

## Step 1: Google Cloud 프로젝트 설정

```bash
# 1. 프로젝트 생성 (또는 기존 프로젝트 사용)
gcloud projects create chaldeas-prod --name="CHALDEAS"

# 2. 프로젝트 선택
gcloud config set project chaldeas-prod

# 3. 결제 계정 연결 (필수)
gcloud billing accounts list
gcloud billing projects link chaldeas-prod --billing-account=YOUR_BILLING_ACCOUNT_ID

# 4. 필요한 API 활성화
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com
```

---

## Step 2: Cloud SQL 설정 (PostgreSQL + pgvector)

```bash
# 1. Cloud SQL 인스턴스 생성 (db-g1-small 권장)
gcloud sql instances create chaldeas-db \
  --database-version=POSTGRES_15 \
  --tier=db-g1-small \
  --region=asia-northeast3 \
  --storage-size=10GB \
  --storage-type=SSD \
  --database-flags=cloudsql.enable_pgvector=on

# 2. 데이터베이스 생성
gcloud sql databases create chaldeas --instance=chaldeas-db

# 3. 사용자 생성
gcloud sql users create chaldeas \
  --instance=chaldeas-db \
  --password=YOUR_SECURE_PASSWORD

# 4. pgvector 확장 활성화 (Cloud SQL에 접속 후)
gcloud sql connect chaldeas-db --user=chaldeas
# SQL> CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Step 3: Secret Manager 설정

```bash
# 1. 데이터베이스 URL 저장
echo -n "postgresql://chaldeas:YOUR_PASSWORD@/chaldeas?host=/cloudsql/chaldeas-prod:asia-northeast3:chaldeas-db" | \
  gcloud secrets create chaldeas-database-url --data-file=-

# 2. OpenAI API Key 저장
echo -n "sk-your-openai-api-key" | \
  gcloud secrets create chaldeas-openai-key --data-file=-

# 3. Anthropic API Key 저장
echo -n "sk-ant-your-anthropic-api-key" | \
  gcloud secrets create chaldeas-anthropic-key --data-file=-

# 4. Cloud Run 서비스 계정에 권한 부여
PROJECT_NUMBER=$(gcloud projects describe chaldeas-prod --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding chaldeas-database-url \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding chaldeas-openai-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding chaldeas-anthropic-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Step 4: 수동 배포 (처음 한 번)

```bash
# 프로젝트 루트에서 실행

# 1. Backend 빌드 및 배포
gcloud builds submit --tag gcr.io/chaldeas-prod/chaldeas-backend backend \
  --dockerfile=backend/Dockerfile.prod

gcloud run deploy chaldeas-backend \
  --image gcr.io/chaldeas-prod/chaldeas-backend \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --set-secrets "DATABASE_URL=chaldeas-database-url:latest,OPENAI_API_KEY=chaldeas-openai-key:latest,ANTHROPIC_API_KEY=chaldeas-anthropic-key:latest" \
  --add-cloudsql-instances chaldeas-prod:asia-northeast3:chaldeas-db

# 2. Backend URL 확인
BACKEND_URL=$(gcloud run services describe chaldeas-backend --region asia-northeast3 --format='value(status.url)')
echo "Backend URL: $BACKEND_URL"

# 3. Frontend 빌드 및 배포
gcloud builds submit --tag gcr.io/chaldeas-prod/chaldeas-frontend frontend \
  --dockerfile=frontend/Dockerfile.prod \
  --build-arg VITE_API_URL=$BACKEND_URL

gcloud run deploy chaldeas-frontend \
  --image gcr.io/chaldeas-prod/chaldeas-frontend \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated \
  --memory 256Mi

# 4. Frontend URL 확인
gcloud run services describe chaldeas-frontend --region asia-northeast3 --format='value(status.url)'
```

---

## Step 5: CI/CD 설정 (자동 배포)

### Option A: Cloud Build Trigger

```bash
# 1. GitHub 저장소 연결
# Cloud Console > Cloud Build > 트리거 > 저장소 연결

# 2. 트리거 생성
gcloud builds triggers create github \
  --repo-name=CHALDEAS \
  --repo-owner=medraud94private \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --substitutions=_BACKEND_URL=https://chaldeas-backend-xxxxx.run.app
```

### Option B: GitHub Actions

`.github/workflows/deploy.yml` 생성:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

env:
  PROJECT_ID: chaldeas-prod
  REGION: asia-northeast3

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Build and Deploy
        run: |
          gcloud builds submit --config cloudbuild.yaml \
            --substitutions=_BACKEND_URL=${{ secrets.BACKEND_URL }}
```

---

## Step 6: 데이터 마이그레이션

```bash
# 1. 로컬에서 Cloud SQL Proxy 실행
cloud-sql-proxy chaldeas-prod:asia-northeast3:chaldeas-db &

# 2. 데이터베이스 마이그레이션 (백엔드 스크립트 실행)
cd backend
python -m app.scripts.init_db

# 3. 기존 데이터 임포트
python -m app.scripts.import_data --source ../data/json
```

---

## 비용 최적화 팁

### 1. min-instances=0 설정

```bash
gcloud run services update chaldeas-backend \
  --min-instances=0 \
  --region asia-northeast3
```

### 2. Cloud SQL 자동 중지 (개발 환경)

```bash
# 인스턴스 중지 (수동)
gcloud sql instances patch chaldeas-db --activation-policy=NEVER

# 인스턴스 시작
gcloud sql instances patch chaldeas-db --activation-policy=ALWAYS
```

### 3. 트래픽 기반 스케일링

```bash
gcloud run services update chaldeas-backend \
  --max-instances=10 \
  --concurrency=80
```

---

## 모니터링 및 로깅

```bash
# Cloud Run 로그 확인
gcloud run services logs read chaldeas-backend --region asia-northeast3

# Cloud SQL 모니터링
gcloud sql operations list --instance=chaldeas-db
```

---

## 커스텀 도메인 설정 (선택)

```bash
# 1. 도메인 매핑
gcloud run domain-mappings create \
  --service chaldeas-frontend \
  --domain chaldeas.yourdomain.com \
  --region asia-northeast3

# 2. DNS 설정 안내 확인
gcloud run domain-mappings describe \
  --domain chaldeas.yourdomain.com \
  --region asia-northeast3
```

---

## 트러블슈팅

### Cloud SQL 연결 실패

```bash
# Cloud SQL Admin API 활성화 확인
gcloud services list --enabled | grep sqladmin

# 서비스 계정 권한 확인
gcloud projects get-iam-policy chaldeas-prod \
  --format='table(bindings.role)' \
  --filter="bindings.members:compute@developer.gserviceaccount.com"
```

### Cold Start 최적화

```bash
# 최소 인스턴스 1개 유지 (비용 증가)
gcloud run services update chaldeas-backend \
  --min-instances=1 \
  --region asia-northeast3
```

---

## 예상 월 비용 (프로덕션)

| 서비스 | 스펙 | 예상 비용 |
|--------|------|-----------|
| Cloud Run (Backend) | 1 vCPU, 1GB | $15-30 |
| Cloud Run (Frontend) | 1 vCPU, 256MB | $5-10 |
| Cloud SQL | db-g1-small | $25-35 |
| Secret Manager | 3 secrets | ~$0.10 |
| Container Registry | ~1GB | ~$0.10 |
| **합계** | | **$45-75/월** |

무료 티어 활용 시: **$10-30/월** 가능
