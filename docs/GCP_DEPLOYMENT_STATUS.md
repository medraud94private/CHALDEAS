# CHALDEAS GCP 배포 진행 상황

**최종 업데이트**: 2025-12-31 16:30 KST

---

## 현재 상태 요약

```
진행률: █████████░ 90%

[✅ 완료] 프로젝트 설정 및 기본 API
[✅ 완료] Cloud SQL 데이터베이스 (chaldeas-db)
[✅ 완료] pgvector 확장
[✅ 완료] Secret Manager
[✅ 완료] cloudbuild.yaml 설정
[⏳ 대기] Cloud Build 배포 실행
```

---

## 1. 완료된 항목 ✅

### 1.1 GCP 프로젝트 설정
| 항목 | 상태 | 값 |
|------|------|-----|
| 프로젝트 ID | ✅ | `chaldeas-archive` |
| 리전 | ✅ | `asia-northeast3` (서울) |
| 인증 계정 | ✅ | `admin@rout.dev` |
| 프로젝트 번호 | ✅ | `951004107180` |

### 1.2 활성화된 API
- ✅ `cloudbuild.googleapis.com` - Cloud Build
- ✅ `run.googleapis.com` - Cloud Run
- ✅ `containerregistry.googleapis.com` - Container Registry
- ✅ `artifactregistry.googleapis.com` - Artifact Registry
- ✅ `sqladmin.googleapis.com` - Cloud SQL Admin
- ✅ `secretmanager.googleapis.com` - Secret Manager

### 1.2.1 Artifact Registry
| 항목 | 값 |
|------|-----|
| 저장소 이름 | `chaldeas` |
| 위치 | `asia-northeast3` |
| 형식 | Docker |
| 이미지 경로 | `asia-northeast3-docker.pkg.dev/chaldeas-archive/chaldeas/` |

### 1.3 Cloud SQL 데이터베이스
| 항목 | 값 |
|------|-----|
| 인스턴스 이름 | `chaldeas-db` |
| 버전 | PostgreSQL 15 |
| 티어 | `db-g1-small` |
| Public IP | `34.22.103.164` |
| Connection Name | `chaldeas-archive:asia-northeast3:chaldeas-db` |
| 데이터베이스 | `chaldeas` |
| 사용자 | `chaldeas` |
| 비밀번호 | `qj3sXK5A0jjqFjW_-uu4HCze` |
| pgvector | ✅ 활성화됨 |

### 1.4 Secret Manager
| 시크릿 이름 | 내용 |
|-------------|------|
| `chaldeas-database-url` | PostgreSQL 연결 문자열 (Cloud SQL 소켓 방식) |
| `chaldeas-openai-key` | OpenAI API 키 |

### 1.5 IAM 권한 설정
- ✅ Compute 서비스 계정 → Secret Manager 접근
- ✅ Cloud Build 서비스 계정 → Cloud Run Admin
- ✅ Cloud Build 서비스 계정 → Service Account User
- ✅ Cloud Build 서비스 계정 → Cloud SQL Client

### 1.6 배포 설정 파일
- ✅ `cloudbuild.yaml` - Cloud Build 파이프라인 (Secret/SQL 연결 추가됨)
- ✅ `deploy.ps1` - PowerShell 배포 스크립트
- ✅ `backend/Dockerfile` - 백엔드 이미지
- ✅ `frontend/Dockerfile.prod` - 프로덕션 프론트엔드

---

## 2. 남은 작업

### 2.1 배포 실행 (약 10-15분)
```powershell
# 프로젝트 루트에서 실행
.\deploy.ps1

# 또는 직접 실행
gcloud builds submit --config=cloudbuild.yaml --timeout=1800s
```

### 2.2 데이터 마이그레이션 (배포 후)
로컬 DB 데이터를 Cloud SQL로 이전해야 함.

**Option A: 인덱싱 스크립트 재실행 (추천)**
```bash
# Cloud SQL 대상으로 데이터 인덱싱
export DATABASE_URL="postgresql://chaldeas:qj3sXK5A0jjqFjW_-uu4HCze@34.22.103.164:5432/chaldeas"
python backend/app/scripts/index_events.py
```

**Option B: 로컬 DB 덤프 & 복원**
```bash
# 1. 로컬 DB 덤프 (로컬 PostgreSQL 실행 필요)
pg_dump -h localhost -p 5433 -U chaldeas -d chaldeas > backup.sql

# 2. Cloud SQL에 복원
export PGPASSWORD="qj3sXK5A0jjqFjW_-uu4HCze"
psql -h 34.22.103.164 -U chaldeas -d chaldeas < backup.sql
```

**데이터 위치:**
- Raw 데이터: `data/raw/` (JSON)
- 처리된 데이터: `data/processed/` (JSON)

---

## 3. 주요 접속 정보

### Cloud SQL 직접 접속
```bash
export PGPASSWORD="qj3sXK5A0jjqFjW_-uu4HCze"
psql -h 34.22.103.164 -U chaldeas -d chaldeas
```

### 상태 확인 명령어
```bash
# Cloud SQL 상태
gcloud sql instances describe chaldeas-db --format="value(state)"

# Cloud Run 서비스 목록
gcloud run services list --region=asia-northeast3

# 빌드 히스토리
gcloud builds list --limit=5

# 시크릿 목록
gcloud secrets list
```

---

## 4. 예상 비용

| 서비스 | 스펙 | 월 예상 |
|--------|------|---------|
| Cloud SQL | db-g1-small | $25-35 |
| Cloud Run (Backend) | 1vCPU, 1GB | $15-30 |
| Cloud Run (Frontend) | 1vCPU, 256MB | $5-10 |
| Secret Manager | 2-3 secrets | ~$0.10 |
| **합계** | | **$45-75** |

> 무료 티어 활용 시 $10-30/월 가능

---

## 5. 배포 후 URL (예정)

```
Frontend: https://chaldeas-frontend-xxxxx-an.a.run.app
Backend:  https://chaldeas-backend-xxxxx-an.a.run.app
API Docs: https://chaldeas-backend-xxxxx-an.a.run.app/docs
```

배포 후 URL 확인:
```bash
gcloud run services describe chaldeas-backend --region=asia-northeast3 --format="value(status.url)"
gcloud run services describe chaldeas-frontend --region=asia-northeast3 --format="value(status.url)"
```

---

## 6. 트러블슈팅

### Cloud SQL 연결 실패 시
```bash
# IP 화이트리스트 확인 (임시 5분)
gcloud sql connect chaldeas-db --user=chaldeas

# 또는 영구 IP 추가
gcloud sql instances patch chaldeas-db --authorized-networks=YOUR_IP/32
```

### 로그 확인
```bash
gcloud run services logs read chaldeas-backend --region=asia-northeast3 --limit=50
```
