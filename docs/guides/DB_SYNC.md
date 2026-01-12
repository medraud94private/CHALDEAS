# DB 동기화 가이드

로컬 DB ↔ Cloud SQL 동기화 방법

## 사전 준비 (최초 1회)

### 1. Cloud SQL Proxy 설치

```powershell
# 다운로드
curl -o cloud-sql-proxy.exe https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.1/cloud-sql-proxy.x64.exe

# PATH에 추가하거나 C:\tools\ 에 복사
move cloud-sql-proxy.exe C:\tools\
```

### 2. GCP 인증

```powershell
gcloud auth login
gcloud config set project chaldeas-archive
```

### 3. Cloud DB 비밀번호 확인

```powershell
gcloud secrets versions access latest --secret=chaldeas-database-url
# 또는 GCP 콘솔 > Secret Manager에서 확인
```

---

## 사용법

### 스크립트로 간단하게

```powershell
# 로컬 → 클라우드 (내 작업 올리기)
.\scripts\sync-db.ps1 up

# 클라우드 → 로컬 (클라우드 데이터 내리기)
.\scripts\sync-db.ps1 down
```

---

## 수동으로 하기 (스크립트 안 쓸 때)

### 로컬 → 클라우드

```powershell
# 1. Proxy 시작 (터미널 1)
cloud-sql-proxy chaldeas-archive:asia-northeast3:chaldeas-db --port=5433

# 2. 덤프 & 복원 (터미널 2)
$env:PGPASSWORD="chaldeas_dev"
pg_dump -U chaldeas -h localhost -p 5432 -d chaldeas > dump.sql

psql -U chaldeas -h localhost -p 5433 -d chaldeas < dump.sql
# (Cloud DB 비밀번호 입력)
```

### 클라우드 → 로컬

```powershell
# 1. Proxy 시작 (터미널 1)
cloud-sql-proxy chaldeas-archive:asia-northeast3:chaldeas-db --port=5433

# 2. 덤프 & 복원 (터미널 2)
pg_dump -U chaldeas -h localhost -p 5433 -d chaldeas > cloud_dump.sql
# (Cloud DB 비밀번호 입력)

$env:PGPASSWORD="chaldeas_dev"
psql -U chaldeas -h localhost -p 5432 -d chaldeas < cloud_dump.sql
```

---

## 한 줄 명령어 (Proxy 이미 실행 중일 때)

```powershell
# 로컬 → 클라우드
$env:PGPASSWORD="chaldeas_dev"; pg_dump -U chaldeas -h localhost -p 5432 chaldeas | psql -U chaldeas -h localhost -p 5433 chaldeas

# 클라우드 → 로컬
pg_dump -U chaldeas -h localhost -p 5433 chaldeas | psql -U chaldeas -h localhost -p 5432 chaldeas
```

---

## 포트 정리

| 용도 | 포트 |
|------|------|
| 로컬 PostgreSQL | 5432 |
| Cloud SQL Proxy | 5433 |

---

## 문제 해결

### "connection refused" 에러
→ Cloud SQL Proxy가 안 돌고 있음. 먼저 시작하세요.

### "permission denied" 에러
→ `gcloud auth login` 다시 실행

### "database does not exist" 에러
→ Cloud SQL에 DB가 없음. GCP 콘솔에서 확인

---

## GCP 정보

- **프로젝트**: `chaldeas-archive`
- **리전**: `asia-northeast3`
- **Cloud SQL 인스턴스**: `chaldeas-db`
- **DB 이름**: `chaldeas`
- **DB 유저**: `chaldeas`
