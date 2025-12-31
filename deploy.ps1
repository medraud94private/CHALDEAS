# CHALDEAS Deployment Script for Google Cloud
# Project: chaldeas-archive
# Run: .\deploy.ps1

$ErrorActionPreference = "Stop"

$PROJECT_ID = "chaldeas-archive"
$REGION = "asia-northeast3"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CHALDEAS Deployment to Google Cloud" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check gcloud
Write-Host "[1/6] Checking gcloud CLI..." -ForegroundColor Yellow
try {
    gcloud --version | Select-Object -First 1
} catch {
    Write-Host "ERROR: gcloud not found. Please install Google Cloud SDK first." -ForegroundColor Red
    exit 1
}

# Step 2: Set project
Write-Host "[2/6] Setting project: $PROJECT_ID" -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Step 3: Enable APIs
Write-Host "[3/6] Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com

# Step 4: Copy data to backend for build
Write-Host "[4/6] Preparing data for deployment..." -ForegroundColor Yellow
if (Test-Path "backend\data") {
    Remove-Item -Recurse -Force "backend\data"
}
Copy-Item -Recurse "data" "backend\data"

# Step 5: Submit Cloud Build
Write-Host "[5/6] Starting Cloud Build (this takes ~10-15 minutes)..." -ForegroundColor Yellow
gcloud builds submit --config=cloudbuild.yaml --timeout=1800s

# Step 6: Get URLs
Write-Host "[6/6] Getting service URLs..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$BACKEND_URL = gcloud run services describe chaldeas-backend --region $REGION --format="value(status.url)" 2>$null
$FRONTEND_URL = gcloud run services describe chaldeas-frontend --region $REGION --format="value(status.url)" 2>$null

Write-Host "Frontend: $FRONTEND_URL" -ForegroundColor Cyan
Write-Host "Backend:  $BACKEND_URL" -ForegroundColor Cyan
Write-Host "API Docs: $BACKEND_URL/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: Connect chaldeas.site domain" -ForegroundColor Yellow

# Cleanup
Remove-Item -Recurse -Force "backend\data" -ErrorAction SilentlyContinue
