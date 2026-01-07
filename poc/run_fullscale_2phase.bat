@echo off
chcp 65001 >nul 2>&1
cd /d C:\Projects\Chaldeas\poc

echo ====================================================
echo CHALDEAS Archivist - 2-Phase Full Processing
echo ====================================================
echo.
echo Phase 1: Fast mode (rule-based) - ~17 hours
echo Phase 2: LLM review of PENDING items - ~1-2 days
echo Total: ~3 days
echo.
echo Start Time: %date% %time%
echo.

REM Environment settings
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"

REM Create logs directory
if not exist logs mkdir logs

REM Log file with timestamp
set "LOGFILE=logs\fullscale_2phase_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log"
set "LOGFILE=%LOGFILE: =0%"

echo Log file: %LOGFILE%
echo.

REM ============================================
REM PHASE 1: Fast Mode (Rule-based matching)
REM ============================================
echo [PHASE 1] Fast mode processing (no LLM)...
echo [PHASE 1] Starting fast mode processing >> "%LOGFILE%"

:PHASE1_LOOP
echo [%date% %time%] Running Phase 1...
python -u scripts/archivist_fullscale.py --save-interval 100 >> "%LOGFILE%" 2>&1

set "EXIT_CODE=%errorlevel%"
echo [%date% %time%] Phase 1 exit code: %EXIT_CODE% >> "%LOGFILE%"

if %EXIT_CODE% neq 0 (
    echo [%date% %time%] Phase 1 interrupted, resuming in 30 seconds...
    timeout /t 30 /nobreak >nul
    goto PHASE1_LOOP
)

echo [%date% %time%] Phase 1 completed!
echo.

REM ============================================
REM PHASE 2: LLM Mode (Qwen for PENDING items)
REM ============================================
echo [PHASE 2] LLM mode for PENDING items...
echo [PHASE 2] Starting LLM review >> "%LOGFILE%"

REM Check Ollama is running for Phase 2
echo Checking Ollama for Phase 2...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start /b ollama serve
    timeout /t 15 /nobreak >nul
)

:PHASE2_LOOP
echo [%date% %time%] Running Phase 2 (LLM review)...
python -u scripts/archivist_review_pending.py >> "%LOGFILE%" 2>&1

set "EXIT_CODE=%errorlevel%"
echo [%date% %time%] Phase 2 exit code: %EXIT_CODE% >> "%LOGFILE%"

if %EXIT_CODE% neq 0 (
    echo [%date% %time%] Phase 2 interrupted, resuming in 60 seconds...
    timeout /t 60 /nobreak >nul
    goto PHASE2_LOOP
)

echo.
echo ====================================================
echo ALL PHASES COMPLETED: %date% %time%
echo Results: poc\data\archivist_results\
echo Log: %LOGFILE%
echo ====================================================
pause
