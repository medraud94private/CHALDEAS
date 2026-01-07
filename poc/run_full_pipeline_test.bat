@echo off
echo ============================================================
echo        ARCHIVIST FULL PIPELINE (TEST MODE)
echo        Processing 100 files only
echo ============================================================
echo.

cd /d "%~dp0"

python scripts/run_archivist_full.py --limit 100 --reset

pause
