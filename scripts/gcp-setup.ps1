# CHALDEAS GCP 설정 스크립트
# Cloud SQL 생성 완료 후 실행

$ErrorActionPreference = "Stop"

$PROJECT_ID = "chaldeas-archive"
$REGION = "asia-northeast3"
$INSTANCE_NAME = "chaldeas-db"
$DB_NAME = "chaldeas"
$DB_USER = "chaldeas"
$DB_PASSWORD = $env:CHALDEAS_DB_PASSWORD  # Set via environment variable
$OPENAI_KEY = $env:OPENAI_API_KEY  # Set via environment variable

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CHALDEAS GCP Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Cloud SQL 상태 확인
Write-Host "`n[1/5] Cloud SQL 인스턴스 상태 확인..." -ForegroundColor Yellow
$status = gcloud sql instances describe $INSTANCE_NAME --format="value(state)" 2>$null
if ($status -ne "RUNNABLE") {
    Write-Host "ERROR: Cloud SQL 인스턴스가 아직 준비되지 않았습니다. 상태: $status" -ForegroundColor Red
    Write-Host "잠시 후 다시 시도해주세요." -ForegroundColor Red
    exit 1
}
Write-Host "OK - 인스턴스 준비됨" -ForegroundColor Green

# Step 2: 데이터베이스 생성
Write-Host "`n[2/5] 데이터베이스 생성..." -ForegroundColor Yellow
gcloud sql databases create $DB_NAME --instance=$INSTANCE_NAME 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - 데이터베이스 생성됨" -ForegroundColor Green
} else {
    Write-Host "SKIP - 데이터베이스가 이미 존재함" -ForegroundColor Yellow
}

# Step 3: 사용자 생성
Write-Host "`n[3/5] 데이터베이스 사용자 생성..." -ForegroundColor Yellow
gcloud sql users create $DB_USER --instance=$INSTANCE_NAME --password=$DB_PASSWORD 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - 사용자 생성됨" -ForegroundColor Green
} else {
    Write-Host "SKIP - 사용자가 이미 존재함" -ForegroundColor Yellow
}

# Step 4: Secret Manager 시크릿 생성
Write-Host "`n[4/5] Secret Manager 설정..." -ForegroundColor Yellow

# DATABASE_URL
$DB_URL = "postgresql://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"
$existingSecret = gcloud secrets describe chaldeas-database-url 2>$null
if (-not $existingSecret) {
    Write-Output $DB_URL | gcloud secrets create chaldeas-database-url --data-file=-
    Write-Host "OK - DATABASE_URL 시크릿 생성됨" -ForegroundColor Green
} else {
    Write-Output $DB_URL | gcloud secrets versions add chaldeas-database-url --data-file=-
    Write-Host "OK - DATABASE_URL 시크릿 업데이트됨" -ForegroundColor Green
}

# OPENAI_API_KEY
$existingSecret = gcloud secrets describe chaldeas-openai-key 2>$null
if (-not $existingSecret) {
    Write-Output $OPENAI_KEY | gcloud secrets create chaldeas-openai-key --data-file=-
    Write-Host "OK - OPENAI_API_KEY 시크릿 생성됨" -ForegroundColor Green
} else {
    Write-Output $OPENAI_KEY | gcloud secrets versions add chaldeas-openai-key --data-file=-
    Write-Host "OK - OPENAI_API_KEY 시크릿 업데이트됨" -ForegroundColor Green
}

# 권한 부여
Write-Host "`n[4.1] 서비스 계정 권한 설정..." -ForegroundColor Yellow
$PROJECT_NUMBER = (gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
$SA = "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding chaldeas-database-url `
    --member="serviceAccount:$SA" `
    --role="roles/secretmanager.secretAccessor" --quiet 2>$null

gcloud secrets add-iam-policy-binding chaldeas-openai-key `
    --member="serviceAccount:$SA" `
    --role="roles/secretmanager.secretAccessor" --quiet 2>$null

Write-Host "OK - 권한 설정 완료" -ForegroundColor Green

# Step 5: 완료
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  GCP 설정 완료!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계: pgvector 확장 활성화" -ForegroundColor Cyan
Write-Host "  gcloud sql connect $INSTANCE_NAME --user=$DB_USER" -ForegroundColor White
Write-Host "  SQL> CREATE EXTENSION IF NOT EXISTS vector;" -ForegroundColor White
Write-Host ""
Write-Host "그 다음: 배포 실행" -ForegroundColor Cyan
Write-Host "  .\deploy.ps1" -ForegroundColor White
