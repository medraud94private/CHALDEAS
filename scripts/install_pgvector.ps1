# pgvector 자동 설치 스크립트 (PowerShell - 관리자 권한)
# 사용법: 관리자 권한 PowerShell에서 실행
#   .\scripts\install_pgvector.ps1

param(
    [string]$PgVersion = "18",
    [string]$PgVectorVersion = "0.8.1"
)

$ErrorActionPreference = "Stop"

# 설정
$ReleaseTag = "${PgVectorVersion}_${PgVersion}.0.2"
$DownloadUrl = "https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/$ReleaseTag/vector.v$PgVectorVersion-pg$PgVersion.zip"

# PostgreSQL 경로 찾기
$PgPaths = @(
    "C:\Program Files\PostgreSQL\$PgVersion",
    "C:\PostgreSQL\$PgVersion"
)

$PgPath = $null
foreach ($path in $PgPaths) {
    if (Test-Path $path) {
        $PgPath = $path
        break
    }
}

if (-not $PgPath) {
    Write-Error "PostgreSQL $PgVersion 설치를 찾을 수 없습니다."
    exit 1
}

Write-Host "=" * 50
Write-Host "pgvector 자동 설치 스크립트"
Write-Host "=" * 50
Write-Host "PostgreSQL 경로: $PgPath"
Write-Host "pgvector 버전: $PgVectorVersion"
Write-Host ""

# 관리자 권한 확인
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "관리자 권한이 필요합니다. 관리자 권한으로 다시 실행합니다..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -PgVersion $PgVersion -PgVectorVersion $PgVectorVersion"
    exit
}

# 임시 디렉토리
$TempDir = Join-Path $env:TEMP "pgvector_install"
if (Test-Path $TempDir) {
    Remove-Item -Recurse -Force $TempDir
}
New-Item -ItemType Directory -Path $TempDir | Out-Null

$ZipPath = Join-Path $TempDir "pgvector.zip"
$ExtractPath = Join-Path $TempDir "extracted"

# 다운로드
Write-Host "다운로드 중: $DownloadUrl"
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
    Write-Host "다운로드 완료!" -ForegroundColor Green
} catch {
    Write-Error "다운로드 실패: $_"
    Write-Host "수동 다운로드: https://github.com/andreiramani/pgvector_pgsql_windows/releases/tag/$ReleaseTag"
    exit 1
}

# 압축 해제
Write-Host "압축 해제 중..."
Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath -Force

# 파일 복사
$LibDir = Join-Path $PgPath "lib"
$ExtDir = Join-Path $PgPath "share\extension"

$filesCopied = 0

Get-ChildItem -Path $ExtractPath -Recurse -File | ForEach-Object {
    $file = $_

    if ($file.Name -eq "vector.dll") {
        $dest = Join-Path $LibDir $file.Name
        Write-Host "복사: $($file.Name) -> $dest"
        Copy-Item -Path $file.FullName -Destination $dest -Force
        $filesCopied++
    }
    elseif ($file.Name -match "\.control$|\.sql$") {
        $dest = Join-Path $ExtDir $file.Name
        Write-Host "복사: $($file.Name) -> $dest"
        Copy-Item -Path $file.FullName -Destination $dest -Force
        $filesCopied++
    }
}

Write-Host ""
Write-Host "$filesCopied 개 파일 설치 완료" -ForegroundColor Green

# 정리
Remove-Item -Recurse -Force $TempDir

# PostgreSQL 확장 생성
$PsqlPath = Join-Path $PgPath "bin\psql.exe"
$Database = "chaldeas"

Write-Host ""
Write-Host "데이터베이스 설정 중..."

# 데이터베이스 존재 확인
$dbExists = & $PsqlPath -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$Database'" 2>$null

if ($dbExists -notmatch "1") {
    Write-Host "데이터베이스 '$Database' 생성 중..."
    & $PsqlPath -U postgres -c "CREATE DATABASE $Database"
}

# 확장 생성
Write-Host "pgvector 확장 생성 중..."
& $PsqlPath -U postgres -d $Database -c "CREATE EXTENSION IF NOT EXISTS vector"

# 확인
$version = & $PsqlPath -U postgres -d $Database -tc "SELECT extversion FROM pg_extension WHERE extname = 'vector'"

if ($version) {
    Write-Host ""
    Write-Host "=" * 50
    Write-Host "pgvector $($version.Trim()) 설치 완료!" -ForegroundColor Green
    Write-Host "데이터베이스: $Database" -ForegroundColor Green
    Write-Host "=" * 50
} else {
    Write-Host "확장 생성 실패. 수동으로 실행하세요:" -ForegroundColor Yellow
    Write-Host "  psql -U postgres -d $Database -c 'CREATE EXTENSION vector;'"
}

Write-Host ""
Write-Host "아무 키나 누르면 종료합니다..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
