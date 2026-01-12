# CHALDEAS DB Sync Script (via GCS)
# Usage: .\scripts\sync-db.ps1 up

param(
    [Parameter(Position=0)]
    [ValidateSet("up", "down", "status")]
    [string]$Direction = "status"
)

$GCP_PROJECT = "chaldeas-archive"
$GCP_REGION = "asia-northeast3"
$CLOUD_SQL_INSTANCE = "chaldeas-db"
$DB_NAME = "chaldeas"
$GCS_BUCKET = "gs://${GCP_PROJECT}-db-sync"
$LOCAL_DB_USER = "chaldeas"
$LOCAL_DB_HOST = "localhost"
$LOCAL_DB_PORT = "5432"
$LOCAL_DB_PASSWORD = "chaldeas_dev"
$CLOUD_DB_USER = "chaldeas"
$CLOUD_POSTGRES_USER = "postgres"
$CLOUD_POSTGRES_PASSWORD = "postgres_gcp_2025"
$env:Path += ";C:\Program Files\PostgreSQL\18\bin"

function Sync-Up {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  LOCAL -> CLOUD (via GCS)" -ForegroundColor Cyan
    Write-Host "======================================`n" -ForegroundColor Cyan

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $dumpFile = "chaldeas_sync_$timestamp.sql"
    $gcsPath = "$GCS_BUCKET/$dumpFile"

    # 1. Dump local DB (data only, no psql commands)
    Write-Host "1. Dumping local DB..." -ForegroundColor Yellow
    $env:PGPASSWORD = "chaldeas_dev"
    $tempDump = "temp_dump.sql"
    pg_dump -U $LOCAL_DB_USER -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -d $DB_NAME --data-only --disable-triggers --no-owner --no-acl --no-comments -F p -f $tempDump

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Dump failed!" -ForegroundColor Red
        return
    }

    # Remove incompatible SET commands (fast method using findstr)
    Write-Host "   Filtering incompatible commands..." -ForegroundColor Gray
    cmd /c "findstr /v /i `"transaction_timeout idle_in_transaction_session_timeout`" $tempDump > $dumpFile"
    Remove-Item $tempDump -ErrorAction SilentlyContinue
    Write-Host "   Done: $dumpFile" -ForegroundColor Green

    # 2. Upload to GCS
    Write-Host "2. Uploading to GCS..." -ForegroundColor Yellow
    gcloud storage cp $dumpFile $gcsPath --project=$GCP_PROJECT

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Upload failed!" -ForegroundColor Red
        return
    }
    Write-Host "   Done: $gcsPath" -ForegroundColor Green

    # 3. Import to Cloud SQL
    Write-Host "3. Importing to Cloud SQL..." -ForegroundColor Yellow
    gcloud sql import sql $CLOUD_SQL_INSTANCE $gcsPath --database=$DB_NAME --quiet

    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nImport failed. Check Cloud SQL logs." -ForegroundColor Red
        Write-Host "Dump file: $dumpFile" -ForegroundColor Gray
        Write-Host "GCS file: $gcsPath" -ForegroundColor Gray
        return
    }
    Write-Host "   Import done" -ForegroundColor Green

    # 4. Grant permissions (via Cloud SQL Proxy)
    Write-Host "4. Granting permissions..." -ForegroundColor Yellow
    $proxyPath = "C:\tools\cloud-sql-proxy.exe"

    if (-Not (Test-Path $proxyPath)) {
        Write-Host "   Cloud SQL Proxy not found at $proxyPath" -ForegroundColor Red
        Write-Host "   Skipping permission grant. Run manually:" -ForegroundColor Yellow
        Write-Host "   GRANT ALL ON ALL TABLES IN SCHEMA public TO chaldeas;" -ForegroundColor Gray
    } else {
        # Start proxy in background
        $proxyJob = Start-Job -ScriptBlock {
            param($path, $project, $region, $instance)
            & $path "${project}:${region}:${instance}" --port=5433
        } -ArgumentList $proxyPath, $GCP_PROJECT, $GCP_REGION, $CLOUD_SQL_INSTANCE

        Start-Sleep -Seconds 3

        # Grant permissions
        $env:PGPASSWORD = $CLOUD_POSTGRES_PASSWORD
        $grantSql = "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $CLOUD_DB_USER; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $CLOUD_DB_USER;"
        psql -U $CLOUD_POSTGRES_USER -h localhost -p 5433 -d $DB_NAME -c $grantSql 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "   Permissions granted" -ForegroundColor Green
        } else {
            Write-Host "   Permission grant failed (may already exist)" -ForegroundColor Yellow
        }

        Stop-Job $proxyJob -ErrorAction SilentlyContinue
        Remove-Job $proxyJob -ErrorAction SilentlyContinue
    }

    # 5. Cleanup
    Write-Host "5. Cleaning up..." -ForegroundColor Yellow
    Remove-Item $dumpFile -ErrorAction SilentlyContinue
    gcloud storage rm $gcsPath 2>&1 | Out-Null
    Write-Host "   Done" -ForegroundColor Green

    Write-Host "`n======================================" -ForegroundColor Green
    Write-Host "  SYNC COMPLETE!" -ForegroundColor Green
    Write-Host "======================================`n" -ForegroundColor Green
}

function Sync-Down {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  CLOUD -> LOCAL (via GCS)" -ForegroundColor Cyan
    Write-Host "======================================`n" -ForegroundColor Cyan

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $dumpFile = "chaldeas_cloud_$timestamp.sql"
    $gcsPath = "$GCS_BUCKET/$dumpFile"

    # 1. Export from Cloud SQL
    Write-Host "1. Exporting from Cloud SQL..." -ForegroundColor Yellow
    gcloud sql export sql $CLOUD_SQL_INSTANCE $gcsPath --database=$DB_NAME --quiet

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Export failed!" -ForegroundColor Red
        return
    }
    Write-Host "   Done: $gcsPath" -ForegroundColor Green

    # 2. Download from GCS
    Write-Host "2. Downloading from GCS..." -ForegroundColor Yellow
    gcloud storage cp $gcsPath $dumpFile

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Download failed!" -ForegroundColor Red
        return
    }
    Write-Host "   Done: $dumpFile" -ForegroundColor Green

    # 3. Import to local
    Write-Host "3. Importing to local DB..." -ForegroundColor Yellow
    $env:PGPASSWORD = $LOCAL_DB_PASSWORD
    psql -U $LOCAL_DB_USER -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -d $DB_NAME -f $dumpFile

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nSync complete!" -ForegroundColor Green
        Remove-Item $dumpFile -ErrorAction SilentlyContinue
        gcloud storage rm $gcsPath 2>&1 | Out-Null
    } else {
        Write-Host "`nSync failed." -ForegroundColor Red
    }
}

function Show-Status {
    Write-Host "`n======================================" -ForegroundColor Cyan
    Write-Host "  CHALDEAS DB Sync Tool" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor White
    Write-Host "  .\scripts\sync-db.ps1 up       # Local -> Cloud" -ForegroundColor Gray
    Write-Host "  .\scripts\sync-db.ps1 down     # Cloud -> Local" -ForegroundColor Gray
    Write-Host "  .\scripts\sync-db.ps1 status   # Compare counts" -ForegroundColor Gray
    Write-Host ""

    # Compare Local vs Cloud
    Write-Host "Comparing databases..." -ForegroundColor Yellow

    # Local counts
    $env:PGPASSWORD = $LOCAL_DB_PASSWORD
    $localCounts = psql -U $LOCAL_DB_USER -h $LOCAL_DB_HOST -p $LOCAL_DB_PORT -d $DB_NAME -t -c "SELECT 'events', COUNT(*) FROM events UNION ALL SELECT 'persons', COUNT(*) FROM persons UNION ALL SELECT 'locations', COUNT(*) FROM locations;" 2>$null

    # Cloud counts (via proxy)
    $proxyPath = "C:\tools\cloud-sql-proxy.exe"
    if (Test-Path $proxyPath) {
        $proxyJob = Start-Job -ScriptBlock {
            param($path, $project, $region, $instance)
            & $path "${project}:${region}:${instance}" --port=5433
        } -ArgumentList $proxyPath, $GCP_PROJECT, $GCP_REGION, $CLOUD_SQL_INSTANCE

        Start-Sleep -Seconds 3

        $env:PGPASSWORD = $CLOUD_POSTGRES_PASSWORD
        $cloudCounts = psql -U $CLOUD_POSTGRES_USER -h localhost -p 5433 -d $DB_NAME -t -c "SELECT 'events', COUNT(*) FROM events UNION ALL SELECT 'persons', COUNT(*) FROM persons UNION ALL SELECT 'locations', COUNT(*) FROM locations;" 2>$null

        Stop-Job $proxyJob -ErrorAction SilentlyContinue
        Remove-Job $proxyJob -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "Table      | Local      | Cloud" -ForegroundColor White
        Write-Host "-----------|------------|----------" -ForegroundColor Gray

        $localLines = $localCounts -split "`n" | Where-Object { $_.Trim() }
        $cloudLines = $cloudCounts -split "`n" | Where-Object { $_.Trim() }

        for ($i = 0; $i -lt $localLines.Count; $i++) {
            $localParts = $localLines[$i] -split '\|'
            $cloudParts = $cloudLines[$i] -split '\|'
            $table = $localParts[0].Trim()
            $localCount = $localParts[1].Trim()
            $cloudCount = $cloudParts[1].Trim()
            $match = if ($localCount -eq $cloudCount) { " ✓" } else { " ✗" }
            Write-Host ("{0,-10} | {1,10} | {2,10}{3}" -f $table, $localCount, $cloudCount, $match)
        }
        Write-Host ""
    } else {
        Write-Host "Cloud SQL Proxy not found. Cannot compare." -ForegroundColor Red
    }
}

switch ($Direction) {
    "up" { Sync-Up }
    "down" { Sync-Down }
    "status" { Show-Status }
}
