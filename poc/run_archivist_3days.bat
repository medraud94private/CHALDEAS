@echo off
chcp 65001 >nul 2>&1
cd /d C:\Projects\Chaldeas\poc

echo ====================================================
echo CHALDEAS Archivist - 3-Day Automated Run
echo ====================================================
echo Start Time: %date% %time%
echo.

REM Environment settings
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"
set "SAMPLE_MULTIPLIER=10"

REM Create logs directory if not exists
if not exist logs mkdir logs

REM Log file with timestamp
set "LOGFILE=logs\archivist_3day_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log"
set "LOGFILE=%LOGFILE: =0%"

echo Log file: %LOGFILE%
echo SAMPLE_MULTIPLIER=%SAMPLE_MULTIPLIER%
echo.

REM Check Ollama is running
echo Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama is not running. Please start Ollama first.
    echo Run: ollama serve
    pause
    exit /b 1
)
echo Ollama OK!
echo.

REM Main execution loop with auto-restart on failure
:LOOP
echo [%date% %time%] Starting test run...
echo [%date% %time%] Starting test run... >> "%LOGFILE%"

python -u scripts/test_archivist.py --mode full --multiplier %SAMPLE_MULTIPLIER% >> "%LOGFILE%" 2>&1

set "EXIT_CODE=%errorlevel%"
echo [%date% %time%] Exit code: %EXIT_CODE% >> "%LOGFILE%"

if %EXIT_CODE% neq 0 (
    echo [%date% %time%] ERROR: Test failed with exit code %EXIT_CODE%
    echo [%date% %time%] ERROR: Test failed with exit code %EXIT_CODE% >> "%LOGFILE%"
    echo Waiting 60 seconds before retry...
    timeout /t 60 /nobreak >nul
    goto LOOP
)

echo [%date% %time%] Test completed successfully
echo [%date% %time%] Test completed successfully >> "%LOGFILE%"
echo.
echo ====================================================
echo COMPLETED: %date% %time%
echo Results saved to: poc\data\archivist_results\
echo Log file: %LOGFILE%
echo ====================================================
