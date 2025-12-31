# CHALDEAS 데이터베이스 설정 스크립트
# 관리자 권한 필요

param(
    [string]$DbName = "chaldeas",
    [string]$DbUser = "chaldeas",
    [string]$DbPassword = "chaldeas_dev"
)

$ErrorActionPreference = "Stop"
$PgPath = "C:\Program Files\PostgreSQL\18"
$PgData = "$PgPath\data"
$HbaFile = "$PgData\pg_hba.conf"
$Psql = "$PgPath\bin\psql.exe"

Write-Host "=" * 50
Write-Host "CHALDEAS 데이터베이스 설정"
Write-Host "=" * 50

# 관리자 권한 확인
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "관리자 권한 필요. 재실행합니다..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

# 1. 백업
Write-Host "`n1. pg_hba.conf 백업..."
$BackupFile = "$HbaFile.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $HbaFile $BackupFile
Write-Host "   백업: $BackupFile"

# 2. trust 인증으로 변경
Write-Host "`n2. trust 인증으로 임시 변경..."
$content = Get-Content $HbaFile -Raw
$newContent = $content -replace 'scram-sha-256', 'trust'
Set-Content $HbaFile $newContent -NoNewline
Write-Host "   완료"

# 3. PostgreSQL 재시작
Write-Host "`n3. PostgreSQL 재시작..."
Restart-Service postgresql-x64-18
Start-Sleep -Seconds 3
Write-Host "   완료"

# 4. 데이터베이스/사용자 생성
Write-Host "`n4. 데이터베이스 및 사용자 생성..."

try {
    # 사용자 생성
    & $Psql -U postgres -c "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DbUser') THEN CREATE USER $DbUser WITH PASSWORD '$DbPassword'; END IF; END `$`$;"
    Write-Host "   사용자 '$DbUser' 확인/생성 완료"

    # 데이터베이스 생성
    $dbExists = & $Psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DbName'"
    if ($dbExists -notmatch "1") {
        & $Psql -U postgres -c "CREATE DATABASE $DbName OWNER $DbUser"
        Write-Host "   데이터베이스 '$DbName' 생성 완료"
    } else {
        Write-Host "   데이터베이스 '$DbName' 이미 존재"
    }

    # 권한 부여
    & $Psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DbName TO $DbUser"
    & $Psql -U postgres -d $DbName -c "GRANT ALL ON SCHEMA public TO $DbUser"
    Write-Host "   권한 부여 완료"

    # pgvector 확장 생성
    & $Psql -U postgres -d $DbName -c "CREATE EXTENSION IF NOT EXISTS vector"
    Write-Host "   pgvector 확장 활성화 완료"

    # 확인
    $version = & $Psql -U postgres -d $DbName -tc "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    Write-Host "   pgvector 버전: $($version.Trim())" -ForegroundColor Green

} catch {
    Write-Host "오류: $_" -ForegroundColor Red
}

# 5. 원래 인증으로 복원
Write-Host "`n5. scram-sha-256 인증으로 복원..."
$content = Get-Content $HbaFile -Raw
$newContent = $content -replace 'trust', 'scram-sha-256'
Set-Content $HbaFile $newContent -NoNewline
Write-Host "   완료"

# 6. PostgreSQL 재시작
Write-Host "`n6. PostgreSQL 재시작..."
Restart-Service postgresql-x64-18
Start-Sleep -Seconds 3
Write-Host "   완료"

# 7. 연결 테스트
Write-Host "`n7. 연결 테스트..."
$env:PGPASSWORD = $DbPassword
$testResult = & $Psql -h localhost -U $DbUser -d $DbName -c "SELECT 'Connection OK!' as status" 2>&1

if ($testResult -match "Connection OK") {
    Write-Host "   연결 성공!" -ForegroundColor Green
} else {
    Write-Host "   연결 테스트 결과: $testResult" -ForegroundColor Yellow
}

Write-Host "`n" + "=" * 50
Write-Host "설정 완료!" -ForegroundColor Green
Write-Host "=" * 50
Write-Host "`n연결 정보:"
Write-Host "  Host: localhost"
Write-Host "  Port: 5432"
Write-Host "  Database: $DbName"
Write-Host "  User: $DbUser"
Write-Host "  Password: $DbPassword"
Write-Host "`nDATABASE_URL=postgresql://${DbUser}:${DbPassword}@localhost:5432/${DbName}"

Write-Host "`n아무 키나 누르면 종료..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
