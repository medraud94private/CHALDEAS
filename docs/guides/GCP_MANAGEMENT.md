# GCP 관리 가이드

> CHALDEAS GCP 리소스 접근 및 관리 방법

---

## 프로젝트 정보

| 항목 | 값 |
|------|-----|
| 프로젝트 ID | `chaldeas-archive` |
| 리전 | `asia-northeast3` (서울) |
| 관리자 계정 | `admin@rout.dev` |
| 콘솔 URL | https://console.cloud.google.com/home/dashboard?project=chaldeas-archive |

---

## 1. GCP 접속 방법

### 1.1 웹 콘솔
1. https://console.cloud.google.com 접속
2. 프로젝트 선택: `chaldeas-archive`

### 1.2 CLI (gcloud)
```bash
# 로그인
gcloud auth login

# 프로젝트 설정
gcloud config set project chaldeas-archive
gcloud config set compute/region asia-northeast3

# 설정 확인
gcloud config list
```

---

## 2. 주요 리소스 관리

### 2.1 Cloud SQL (데이터베이스)

**콘솔 접속:**
- https://console.cloud.google.com/sql/instances?project=chaldeas-archive

**CLI 명령어:**
```bash
# 인스턴스 상태 확인
gcloud sql instances describe chaldeas-db

# 시작/중지 (비용 절감)
gcloud sql instances patch chaldeas-db --activation-policy=NEVER  # 중지
gcloud sql instances patch chaldeas-db --activation-policy=ALWAYS # 시작

# 직접 연결
gcloud sql connect chaldeas-db --user=chaldeas --database=chaldeas
```

**psql 직접 연결:**
```bash
export PGPASSWORD="qj3sXK5A0jjqFjW_-uu4HCze"
psql -h 34.22.103.164 -U chaldeas -d chaldeas

# 또는 Windows
$env:PGPASSWORD="qj3sXK5A0jjqFjW_-uu4HCze"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 34.22.103.164 -U chaldeas -d chaldeas
```

### 2.2 Cloud Run (서비스)

**콘솔 접속:**
- https://console.cloud.google.com/run?project=chaldeas-archive

**CLI 명령어:**
```bash
# 서비스 목록
gcloud run services list --region=asia-northeast3

# 서비스 상태
gcloud run services describe chaldeas-backend --region=asia-northeast3
gcloud run services describe chaldeas-frontend --region=asia-northeast3

# 로그 확인
gcloud run services logs read chaldeas-backend --region=asia-northeast3 --limit=50

# 서비스 URL
gcloud run services describe chaldeas-backend --region=asia-northeast3 --format="value(status.url)"
```

### 2.3 Secret Manager

**콘솔 접속:**
- https://console.cloud.google.com/security/secret-manager?project=chaldeas-archive

**CLI 명령어:**
```bash
# 시크릿 목록
gcloud secrets list

# 시크릿 값 확인
gcloud secrets versions access latest --secret=chaldeas-database-url
gcloud secrets versions access latest --secret=chaldeas-openai-key

# 시크릿 추가
gcloud secrets create NEW_SECRET --data-file=./secret.txt
```

### 2.4 Cloud Build

**콘솔 접속:**
- https://console.cloud.google.com/cloud-build/builds?project=chaldeas-archive

**CLI 명령어:**
```bash
# 빌드 히스토리
gcloud builds list --limit=10

# 빌드 로그
gcloud builds log BUILD_ID

# 수동 빌드 실행
gcloud builds submit --config=cloudbuild.yaml
```

---

## 3. 배포

### 3.1 전체 배포 (PowerShell)
```powershell
cd C:\Projects\Chaldeas
.\deploy.ps1
```

### 3.2 수동 배포
```bash
# 백엔드만
gcloud builds submit --config=cloudbuild.yaml --substitutions=_SERVICE=backend

# 전체
gcloud builds submit --config=cloudbuild.yaml --timeout=1800s
```

### 3.3 롤백
```bash
# 이전 리비전으로 롤백
gcloud run services update-traffic chaldeas-backend \
  --to-revisions=REVISION_NAME=100 \
  --region=asia-northeast3
```

---

## 4. 모니터링

### 4.1 대시보드
- https://console.cloud.google.com/monitoring?project=chaldeas-archive

### 4.2 로그 탐색기
- https://console.cloud.google.com/logs?project=chaldeas-archive

### 4.3 CLI로 로그 확인
```bash
# Cloud Run 로그
gcloud logging read "resource.type=cloud_run_revision" --limit=50 --format="table(timestamp,textPayload)"

# Cloud SQL 로그
gcloud logging read "resource.type=cloudsql_database" --limit=50
```

---

## 5. 비용 관리

### 5.1 비용 확인
- https://console.cloud.google.com/billing?project=chaldeas-archive

### 5.2 비용 절감 방법

**Cloud SQL 중지 (사용 안 할 때):**
```bash
gcloud sql instances patch chaldeas-db --activation-policy=NEVER
```

**Cloud Run 최소 인스턴스 0으로:**
```bash
gcloud run services update chaldeas-backend \
  --min-instances=0 \
  --region=asia-northeast3
```

### 5.3 예상 월 비용
| 서비스 | 스펙 | 월 예상 |
|--------|------|---------|
| Cloud SQL | db-g1-small (중지 시 저장소만) | $25-35 |
| Cloud Run | 사용량 기반 | $15-30 |
| 합계 | | $40-65 |

---

## 6. 트러블슈팅

### 6.1 Cloud SQL 연결 실패
```bash
# 현재 IP 확인
curl ifconfig.me

# IP 화이트리스트 추가 (임시)
gcloud sql instances patch chaldeas-db --authorized-networks=YOUR_IP/32

# 또는 프록시 사용
gcloud sql connect chaldeas-db --user=chaldeas
```

### 6.2 Cloud Run 배포 실패
```bash
# 빌드 로그 확인
gcloud builds list --limit=5
gcloud builds log BUILD_ID

# 서비스 로그 확인
gcloud run services logs read chaldeas-backend --region=asia-northeast3
```

### 6.3 권한 오류
```bash
# 현재 인증 확인
gcloud auth list

# 서비스 계정 확인
gcloud iam service-accounts list

# 권한 추가
gcloud projects add-iam-policy-binding chaldeas-archive \
  --member="serviceAccount:XXX@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

---

## 7. 주요 URL 정리

| 서비스 | URL |
|--------|-----|
| GCP 콘솔 | https://console.cloud.google.com/?project=chaldeas-archive |
| Cloud SQL | https://console.cloud.google.com/sql/instances?project=chaldeas-archive |
| Cloud Run | https://console.cloud.google.com/run?project=chaldeas-archive |
| Secret Manager | https://console.cloud.google.com/security/secret-manager?project=chaldeas-archive |
| Cloud Build | https://console.cloud.google.com/cloud-build?project=chaldeas-archive |
| 로그 | https://console.cloud.google.com/logs?project=chaldeas-archive |
| 비용 | https://console.cloud.google.com/billing?project=chaldeas-archive |

---

## 8. 접속 정보 요약

```
Cloud SQL:
  Host: 34.22.103.164
  DB: chaldeas
  User: chaldeas
  Password: qj3sXK5A0jjqFjW_-uu4HCze

Cloud Run (배포 후):
  Backend: https://chaldeas-backend-uh6woizycq-du.a.run.app
  Frontend: https://chaldeas-frontend-xxxxx-an.a.run.app
```
