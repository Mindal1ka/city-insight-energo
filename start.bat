@echo off
chcp 65001 >nul
title City Insight Map :3839
cd /d "%~dp0backend"

rem City Insight Map (pl.mindal1ka.com): FastAPI + built frontend (frontend\build).
rem Kept alive by the starter supervisor (C:\Users\A\Documents\starter\data.txt).
rem The loop restarts the server by itself: scripts\restart.bat checks the code,
rem asks the server to exit, and it comes back here in 2 s without the window closing.

echo.
echo   City Insight Map - Poltava Open Data Hackathon
echo   address  http://127.0.0.1:3839  (Caddy: https://pl.mindal1ka.com)
echo   restart  scripts\restart.bat
echo.

:loop
python -m uvicorn app.main:app --host 127.0.0.1 --port 3839 --proxy-headers --forwarded-allow-ips="*"
echo   server stopped, restarting in 2 s
ping -n 3 127.0.0.1 >nul
goto loop
