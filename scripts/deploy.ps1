# CHALDEAS Deploy Script
# Usage: .\scripts\deploy.ps1 [all|backend|frontend]

param(
    [Parameter(Position=0)]
    [ValidateSet("all", "backend", "frontend", "status")]
    [string]$Target = "status"
)

$GCP_PROJECT = "chaldeas-archive"
$GCP_REGION = "asia-northeast3"

function Deploy-All {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  Deploying ALL (Cloud Build)" -ForegroundColor Cyan
    Write-Host "======================================`n" -ForegroundColor Cyan

    Write-Host "Triggering Cloud Build..." -ForegroundColor Yellow
    gcloud builds submit --config=cloudbuild.yaml --project=$GCP_PROJECT

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nDeploy complete!" -ForegroundColor Green
        Show-URLs
    } else {
        Write-Host "`nDeploy failed. Check Cloud Build logs." -ForegroundColor Red
    }
}

function Deploy-Backend {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  Deploying BACKEND only" -ForegroundColor Cyan
    Write-Host "======================================`n" -ForegroundColor Cyan

    $AR_REPO = "asia-northeast3-docker.pkg.dev/$GCP_PROJECT/chaldeas"
    $SERVICE = "chaldeas-backend"

    # Build
    Write-Host "1. Building backend..." -ForegroundColor Yellow
    Push-Location backend
    Copy-Item -Recurse ..\data .\data -Force -ErrorAction SilentlyContinue
    docker build -t "$AR_REPO/${SERVICE}:latest" .
    Remove-Item -Recurse .\data -Force -ErrorAction SilentlyContinue
    Pop-Location

    # Push
    Write-Host "2. Pushing to Artifact Registry..." -ForegroundColor Yellow
    docker push "$AR_REPO/${SERVICE}:latest"

    # Deploy
    Write-Host "3. Deploying to Cloud Run..." -ForegroundColor Yellow
    gcloud run deploy $SERVICE `
        --image "$AR_REPO/${SERVICE}:latest" `
        --region $GCP_REGION `
        --platform managed `
        --allow-unauthenticated `
        --project $GCP_PROJECT

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nBackend deployed!" -ForegroundColor Green
    }
}

function Deploy-Frontend {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  Deploying FRONTEND only" -ForegroundColor Cyan
    Write-Host "======================================`n" -ForegroundColor Cyan

    $AR_REPO = "asia-northeast3-docker.pkg.dev/$GCP_PROJECT/chaldeas"
    $SERVICE = "chaldeas-frontend"

    # Get backend URL
    $BACKEND_URL = gcloud run services describe chaldeas-backend --region $GCP_REGION --format='value(status.url)' --project $GCP_PROJECT
    Write-Host "Backend URL: $BACKEND_URL" -ForegroundColor Gray

    # Build
    Write-Host "1. Building frontend..." -ForegroundColor Yellow
    Push-Location frontend
    docker build --build-arg VITE_API_URL=$BACKEND_URL -t "$AR_REPO/${SERVICE}:latest" -f Dockerfile.prod .
    Pop-Location

    # Push
    Write-Host "2. Pushing to Artifact Registry..." -ForegroundColor Yellow
    docker push "$AR_REPO/${SERVICE}:latest"

    # Deploy
    Write-Host "3. Deploying to Cloud Run..." -ForegroundColor Yellow
    gcloud run deploy $SERVICE `
        --image "$AR_REPO/${SERVICE}:latest" `
        --region $GCP_REGION `
        --platform managed `
        --allow-unauthenticated `
        --project $GCP_PROJECT

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nFrontend deployed!" -ForegroundColor Green
    }
}

function Show-URLs {
    Write-Host "`n--- Service URLs ---" -ForegroundColor White
    $backend = gcloud run services describe chaldeas-backend --region $GCP_REGION --format='value(status.url)' --project $GCP_PROJECT 2>$null
    $frontend = gcloud run services describe chaldeas-frontend --region $GCP_REGION --format='value(status.url)' --project $GCP_PROJECT 2>$null
    Write-Host "Backend:  $backend" -ForegroundColor Gray
    Write-Host "Frontend: $frontend" -ForegroundColor Gray
}

function Show-Status {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  CHALDEAS Deploy Tool" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor White
    Write-Host "  .\scripts\deploy.ps1 all       # Deploy everything (recommended)" -ForegroundColor Gray
    Write-Host "  .\scripts\deploy.ps1 backend   # Backend only" -ForegroundColor Gray
    Write-Host "  .\scripts\deploy.ps1 frontend  # Frontend only" -ForegroundColor Gray
    Write-Host ""
    Show-URLs
    Write-Host ""
}

switch ($Target) {
    "all" { Deploy-All }
    "backend" { Deploy-Backend }
    "frontend" { Deploy-Frontend }
    "status" { Show-Status }
}
