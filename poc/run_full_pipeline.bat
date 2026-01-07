@echo off
echo ============================================================
echo        ARCHIVIST FULL PIPELINE
echo ============================================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

REM Run the launcher
python scripts/run_archivist_full.py %*

pause
