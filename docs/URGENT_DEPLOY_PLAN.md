# CHALDEAS 긴급 배포 계획서

> **목표**: 오늘 오후 6시까지 GCP에 배포하여 외부 접속 가능하게 만들기
> **현재 시간**: 오후 1시 30분
> **남은 시간**: 4시간 30분

---

## 배포 개요

```
┌─────────────────────────────────────────────────────────────┐
│                      목표 아키텍처                           │
│                                                              │
│   사용자 ──→ Frontend URL ──→ Backend URL ──→ 데이터        │
│              (Cloud Run)      (Cloud Run)    (JSON/SQL)     │
│                                                              │
│   결과물:                                                    │
│   - https://chaldeas-frontend-xxxxx.run.app (프론트엔드)    │
│   - https://chaldeas-backend-xxxxx.run.app  (API)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 타임라인

| 시간 | 작업 | 소요 |
|------|------|------|
| 13:30 - 13:45 | GCP 프로젝트 설정 | 15분 |
| 13:45 - 14:15 | Backend 배포 | 30분 |
| 14:15 - 14:45 | Frontend 배포 | 30분 |
| 14:45 - 15:15 | 데이터 업로드 및 연결 | 30분 |
| 15:15 - 16:00 | 테스트 및 버그 수정 | 45분 |
| 16:00 - 17:00 | 버퍼 시간 (문제 해결) | 60분 |
| 17:00 - 18:00 | 최종 점검 및 준비 | 60분 |

---

## Phase 1: GCP 프로젝트 설정 (15분)

### 1.1 사전 확인

```bash
# gcloud CLI 설치 확인
gcloud --version

# 로그인
gcloud auth login

# 프로젝트 목록 확인
gcloud projects list
```

### 1.2 프로젝트 생성 (없으면)

```bash
# 프로젝트 생성
gcloud projects create chaldeas-demo --name="CHALDEAS Demo"

# 프로젝트 선택
gcloud config set project chaldeas-demo

# 결제 계정 연결 (필수!)
gcloud billing accounts list
gcloud billing projects link chaldeas-demo --billing-account=BILLING_ACCOUNT_ID
```

### 1.3 필수 API 활성화

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  artifactregistry.googleapis.com
```

---

## Phase 2: Backend 배포 (30분)

### 2.1 Backend 이미지 빌드 및 푸시

```bash
cd C:\Projects\Chaldeas

# Container Registry에 이미지 빌드 및 푸시
gcloud builds submit --tag gcr.io/chaldeas-demo/chaldeas-backend ./backend
```

### 2.2 Cloud Run 배포

```bash
gcloud run deploy chaldeas-backend \
  --image gcr.io/chaldeas-demo/chaldeas-backend \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --set-env-vars "ENVIRONMENT=production"
```

### 2.3 Backend URL 확인

```bash
# URL 출력
gcloud run services describe chaldeas-backend \
  --region asia-northeast3 \
  --format='value(status.url)'

# 예: https://chaldeas-backend-xxxxx-du.a.run.app
```

---

## Phase 3: Frontend 배포 (30분)

### 3.1 환경 변수 설정

```bash
# frontend/.env.production 생성
echo "VITE_API_URL=https://chaldeas-backend-xxxxx-du.a.run.app" > frontend/.env.production
```

### 3.2 Frontend 이미지 빌드

```bash
# 프로덕션 빌드
gcloud builds submit \
  --tag gcr.io/chaldeas-demo/chaldeas-frontend \
  --build-arg VITE_API_URL=https://chaldeas-backend-xxxxx-du.a.run.app \
  ./frontend
```

### 3.3 Cloud Run 배포

```bash
gcloud run deploy chaldeas-frontend \
  --image gcr.io/chaldeas-demo/chaldeas-frontend \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1
```

### 3.4 Frontend URL 확인

```bash
gcloud run services describe chaldeas-frontend \
  --region asia-northeast3 \
  --format='value(status.url)'

# 예: https://chaldeas-frontend-xxxxx-du.a.run.app
```

---

## Phase 4: 데이터 설정 (30분)

### 옵션 A: JSON 파일 사용 (빠름, 권장)

현재 `data/json/` 폴더의 데이터를 그대로 사용:

```bash
# Backend Dockerfile에서 data 폴더 복사 확인
# 이미 설정되어 있으면 추가 작업 불필요
```

### 옵션 B: Cloud SQL 사용 (시간 여유 있으면)

```bash
# Cloud SQL 인스턴스 생성 (10분 소요)
gcloud sql instances create chaldeas-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=asia-northeast3

# 데이터베이스 생성
gcloud sql databases create chaldeas --instance=chaldeas-db

# 사용자 생성
gcloud sql users create chaldeas \
  --instance=chaldeas-db \
  --password=YOUR_PASSWORD
```

---

## Phase 5: 테스트 체크리스트

### 필수 테스트

- [ ] Frontend URL 접속 가능
- [ ] 지구본 렌더링 확인
- [ ] Backend API 응답 확인 (`/docs` 접속)
- [ ] 이벤트 마커 표시
- [ ] 검색 기능 동작
- [ ] 타임라인 조작

### 테스트 명령어

```bash
# Backend 헬스체크
curl https://chaldeas-backend-xxxxx-du.a.run.app/health

# API 문서 접속
# 브라우저: https://chaldeas-backend-xxxxx-du.a.run.app/docs

# 이벤트 조회 테스트
curl https://chaldeas-backend-xxxxx-du.a.run.app/api/v1/events
```

---

## 문제 발생 시 대응

### 문제 1: 빌드 실패

```bash
# 로그 확인
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

### 문제 2: 배포 후 502 에러

```bash
# 로그 확인
gcloud run services logs read chaldeas-backend --region asia-northeast3
```

### 문제 3: CORS 에러

Backend에서 CORS 설정 확인:
```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 데모용으로 전체 허용
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 문제 4: 데이터 안 보임

```bash
# Backend 컨테이너 내 데이터 확인
gcloud run services describe chaldeas-backend --region asia-northeast3
```

---

## 최종 결과물

| 항목 | URL |
|------|-----|
| **Frontend** | https://chaldeas-frontend-xxxxx-du.a.run.app |
| **Backend API** | https://chaldeas-backend-xxxxx-du.a.run.app |
| **API 문서** | https://chaldeas-backend-xxxxx-du.a.run.app/docs |

---

## 비상 계획 (Plan B)

시간 부족하면 **ngrok**으로 로컬 노출:

```bash
# 로컬에서 실행
docker-compose up -d

# ngrok으로 외부 노출
ngrok http 5100  # Frontend
ngrok http 8100  # Backend (다른 터미널)
```

---

## 다음 단계 (데모 후)

1. 커스텀 도메인 연결
2. Cloud SQL로 데이터베이스 이전
3. CI/CD 파이프라인 설정
4. 모니터링 및 로깅 설정
