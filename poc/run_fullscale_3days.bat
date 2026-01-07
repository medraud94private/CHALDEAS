@echo off
chcp 65001 >nul 2>&1
cd /d C:\Projects\Chaldeas\poc

echo ====================================================
echo CHALDEAS Archivist - Full-Scale 3-Day Processing
echo ====================================================
echo Start Time: %date% %time%
echo.
echo Target: 76,000+ files (~50GB)
echo Features: Checkpointing, Auto-restart, Resumable
echo.

REM Environment settings
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"

REM Create logs directory
if not exist logs mkdir logs

REM Log file with timestamp
set "LOGFILE=logs\fullscale_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log"
set "LOGFILE=%LOGFILE: =0%"

echo Log file: %LOGFILE%
echo.

REM Check Ollama is running
echo Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama is not running.
    echo Starting Ollama...
    start /b ollama serve
    timeout /t 10 /nobreak >nul
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Could not start Ollama. Please start manually.
        pause
        exit /b 1
    )
)
echo Ollama OK!
echo.

REM Main execution loop with auto-restart on failure
:LOOP
echo [%date% %time%] Starting full-scale processing...
echo [%date% %time%] Starting full-scale processing... >> "%LOGFILE%"

REM Run full-scale processing (checkpointing enabled, resumes automatically)
python -u scripts/archivist_fullscale.py --save-interval 25 >> "%LOGFILE%" 2>&1

set "EXIT_CODE=%errorlevel%"
echo [%date% %time%] Exit code: %EXIT_CODE% >> "%LOGFILE%"

if %EXIT_CODE% neq 0 (
    echo [%date% %time%] Processing interrupted or error occurred
    echo [%date% %time%] Processing interrupted >> "%LOGFILE%"
    echo Waiting 30 seconds before resuming from checkpoint...
    timeout /t 30 /nobreak >nul
    goto LOOP
)

echo [%date% %time%] Processing completed successfully!
echo [%date% %time%] Processing completed successfully! >> "%LOGFILE%"
echo.
echo ====================================================
echo COMPLETED: %date% %time%
echo Results: poc\data\archivist_results\
echo Checkpoint: poc\data\archivist_checkpoint.json
echo Log: %LOGFILE%
echo ====================================================
pause
