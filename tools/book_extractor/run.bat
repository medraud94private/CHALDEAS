@echo off
echo ========================================
echo CHALDEAS Book Extractor
echo ========================================
echo.
echo Starting server at http://localhost:8200
echo.
echo Make sure Ollama is running!
echo   ollama serve
echo   ollama run llama3.1:8b-instruct-q4_0
echo.
echo ========================================
python server.py
pause
