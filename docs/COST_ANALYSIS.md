# CHALDEAS 클라우드 비용 분석

## 개요

Google Cloud Platform 기준 예상 비용을 분석합니다.
실제 비용은 트래픽, 사용 패턴에 따라 달라질 수 있습니다.

---

## 서비스별 비용 상세

### 1. Cloud Run

| 항목 | 무료 티어 | 초과 시 단가 |
|------|-----------|-------------|
| 요청 수 | 200만 요청/월 | $0.40/100만 요청 |
| CPU | 180,000 vCPU-초/월 | $0.000024/vCPU-초 |
| 메모리 | 360,000 GB-초/월 | $0.0000025/GB-초 |
| 네트워크 (아웃바운드) | 1GB/월 | $0.12/GB |

**계산 예시 (Backend)**:
- 1 vCPU, 1GB 메모리
- 하루 평균 2시간 활성화
- 월간: 60시간 = 216,000초

```
CPU:    216,000초 × 1 vCPU × $0.000024 = $5.18
Memory: 216,000초 × 1 GB × $0.0000025 = $0.54
합계: ~$6/월 (무료 티어 적용 시 더 낮음)
```

### 2. Cloud SQL (PostgreSQL)

| 티어 | 스펙 | 월 비용 |
|------|------|---------|
| db-f1-micro | 공유 vCPU, 0.6GB RAM | ~$7 |
| db-g1-small | 공유 vCPU, 1.7GB RAM | ~$25 |
| db-custom-1-3840 | 1 vCPU, 3.75GB RAM | ~$50 |
| db-custom-2-7680 | 2 vCPU, 7.5GB RAM | ~$100 |

**추가 비용**:
- 스토리지: $0.17/GB/월 (SSD)
- 백업: $0.08/GB/월
- 네트워크: 같은 리전 무료

**pgvector 참고**: Cloud SQL PostgreSQL 15+에서 pgvector 확장 기본 지원

### 3. Secret Manager

| 항목 | 무료 티어 | 초과 단가 |
|------|-----------|-----------|
| 시크릿 버전 | 6개 활성 버전 | $0.06/버전/월 |
| 액세스 | 10,000회/월 | $0.03/10,000회 |

→ 거의 무료 (월 $0.10 미만)

### 4. Container Registry / Artifact Registry

| 항목 | 단가 |
|------|------|
| 스토리지 | $0.026/GB/월 |
| 네트워크 | 같은 리전 무료 |

→ 1GB 이미지 기준 월 $0.03

### 5. Cloud Build

| 항목 | 무료 티어 | 초과 단가 |
|------|-----------|-----------|
| 빌드 시간 | 120분/일 | $0.003/분 |

→ 일반적인 사용에서 무료

---

## 시나리오별 총 비용

### 시나리오 1: 개발/테스트 (최소 비용)

트래픽 거의 없음, 혼자 테스트용

```
┌─────────────────────────────────────────┐
│  개발/테스트 환경                         │
├─────────────────────────────────────────┤
│  Cloud Run (Backend)     무료 티어 내    │
│  Cloud Run (Frontend)    무료 티어 내    │
│  Cloud SQL (db-f1-micro) $7            │
│  Secret Manager          ~$0           │
│  Container Registry      ~$0           │
├─────────────────────────────────────────┤
│  월 합계:                ~$7-10        │
└─────────────────────────────────────────┘
```

### 시나리오 2: 소규모 프로덕션

일일 방문자 100-500명

```
┌─────────────────────────────────────────┐
│  소규모 프로덕션                          │
├─────────────────────────────────────────┤
│  Cloud Run (Backend)     $10-15        │
│  Cloud Run (Frontend)    $5-10         │
│  Cloud SQL (db-g1-small) $25-30        │
│  Secret Manager          ~$0.10        │
│  Container Registry      ~$0.10        │
│  네트워크 (5GB)          $0.60         │
├─────────────────────────────────────────┤
│  월 합계:                ~$40-55       │
└─────────────────────────────────────────┘
```

### 시나리오 3: 중규모 프로덕션

일일 방문자 1,000-5,000명, AI 기능 활발 사용

```
┌─────────────────────────────────────────┐
│  중규모 프로덕션                          │
├─────────────────────────────────────────┤
│  Cloud Run (Backend)     $30-50        │
│  Cloud Run (Frontend)    $10-15        │
│  Cloud SQL (db-custom)   $70-100       │
│  Secret Manager          ~$0.50        │
│  Container Registry      ~$0.50        │
│  네트워크 (20GB)         $2.40         │
│  Cloud CDN (선택)        $10-20        │
├─────────────────────────────────────────┤
│  월 합계:                ~$120-190     │
└─────────────────────────────────────────┘
```

### 외부 API 비용 (별도)

| 서비스 | 모델 | 단가 |
|--------|------|------|
| OpenAI | GPT-4o | $2.50/1M 입력, $10/1M 출력 |
| OpenAI | GPT-4o-mini | $0.15/1M 입력, $0.60/1M 출력 |
| OpenAI | text-embedding-3-small | $0.02/1M 토큰 |
| Anthropic | Claude 3.5 Sonnet | $3/1M 입력, $15/1M 출력 |
| Anthropic | Claude 3 Haiku | $0.25/1M 입력, $1.25/1M 출력 |

---

## 비용 최적화 전략

### 1. Cloud Run 최적화

```bash
# min-instances=0으로 유휴 시 비용 절감
gcloud run services update chaldeas-backend \
  --min-instances=0 \
  --max-instances=10

# 동시성 높이기 (인스턴스 수 감소)
gcloud run services update chaldeas-backend \
  --concurrency=100
```

### 2. Cloud SQL 최적화

```bash
# 개발 시간 외 인스턴스 중지
gcloud sql instances patch chaldeas-db --activation-policy=NEVER

# 다시 시작
gcloud sql instances patch chaldeas-db --activation-policy=ALWAYS
```

### 3. 대안 DB 고려 (비용 절감)

| 서비스 | 무료 티어 | pgvector | 비고 |
|--------|-----------|----------|------|
| **Supabase** | 500MB | ✅ | 가장 추천 |
| **Neon** | 3GB | ✅ | 서버리스 |
| **CockroachDB** | 5GB | ❌ | 분산 DB |
| **PlanetScale** | 5GB | ❌ | MySQL 기반 |

### 4. Frontend CDN 분리

```bash
# Firebase Hosting (무료) 또는 Vercel 사용
# 정적 파일만 제공하므로 Cloud Run 불필요
npm run build
firebase deploy --only hosting
```

---

## 비용 vs 대안 비교표

| 구성 | 월 비용 | 장점 | 단점 |
|------|---------|------|------|
| **GCP (최소)** | $7-10 | 통합 환경, 확장성 | Cloud SQL 필수 |
| **GCP (권장)** | $40-55 | 안정성, pgvector | 비용 |
| **Vercel + Supabase** | $0-20 | 무료 시작 가능 | 확장 시 비용 급증 |
| **Railway** | $5-20 | 간편함 | 성능 제한 |
| **Fly.io + Neon** | $0-15 | 저렴, 엣지 배포 | 러닝커브 |
| **VPS (Hetzner)** | $5-10 | 가장 저렴 | 직접 관리 |

---

## 비용 모니터링

### GCP 예산 알림 설정

```bash
# 예산 생성 (월 $50 초과 시 알림)
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="CHALDEAS 월간 예산" \
  --budget-amount=50USD \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0
```

### 비용 대시보드

1. [GCP Billing Console](https://console.cloud.google.com/billing)
2. Reports 탭에서 서비스별 비용 확인
3. 예산 및 알림 설정

---

## 결론

| 목적 | 추천 구성 | 예상 비용 |
|------|-----------|-----------|
| 학습/테스트 | GCP 무료 티어 + Supabase | $0-5/월 |
| 사이드 프로젝트 | Cloud Run + db-f1-micro | $10-20/월 |
| 소규모 서비스 | Cloud Run + db-g1-small | $40-60/월 |
| 프로덕션 | Cloud Run + db-custom + CDN | $100+/월 |
