@echo off
chcp 65001 >nul 2>&1
cd /d C:\Projects\Chaldeas\poc

echo Starting Archivist PoC test at %date% %time%
echo Log file: logs\archivist_overnight.log

REM Set SAMPLE_MULTIPLIER for overnight test (10 = ~340 texts)
set "SAMPLE_MULTIPLIER=10"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"

echo SAMPLE_MULTIPLIER=%SAMPLE_MULTIPLIER%
echo.

python scripts/test_archivist.py --mode full > logs\archivist_overnight.log 2>&1

echo.
echo Test completed at %date% %time%
echo Results saved to: logs\archivist_overnight.log
echo Check also: poc\data\archivist_results\ for JSON results
pause
