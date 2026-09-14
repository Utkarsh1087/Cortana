@echo off
title Lisa - Holographic 3D Avatar Server
cd /d "%~dp0"

echo ===================================================
echo   Starting Lisa 3D Holographic Avatar & Mind...
echo   Open: http://localhost:8000 in your browser
echo ===================================================

:loop
python avatar_server.py
echo.
echo [Warning] Server exited. Restarting Lisa in 2 seconds... (Press Ctrl+C to stop)
timeout /t 2 /nobreak >nul
goto loop

