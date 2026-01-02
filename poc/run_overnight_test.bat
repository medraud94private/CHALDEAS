@echo off
chcp 65001 >nul 2>&1
cd /d C:\Projects\Chaldeas\poc

echo ====================================================
echo CHALDEAS Archivist PoC Overnight Test
echo ====================================================
echo Start Time: %date% %time%
echo.

set "PYTHONUNBUFFERED=1"
set "SAMPLE_MULTIPLIER=10"
set "PYTHONIOENCODING=utf-8"

echo SAMPLE_MULTIPLIER=%SAMPLE_MULTIPLIER%
echo.

python -u scripts/test_archivist.py --mode full

echo.
echo Completed: %date% %time%
pause
