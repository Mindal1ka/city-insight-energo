@echo off
chcp 65001 >nul
rem Safe restart of City Insight Map on :3839, no admin rights needed.
rem 1) checks that the backend code imports and the frontend build exists;
rem    if not, the running server is left untouched;
rem 2) creates .restart-api in the repo root: the server notices it within 2 s, deletes it
rem    and exits; the loop in start.bat (kept alive by starter) starts it again;
rem 3) waits until the new server answers.
rem Usage: scripts\restart.bat
rem (waits use ping, not timeout: timeout fails when there is no console input)
setlocal
set ROOT=%~dp0..
set FLAG=%ROOT%\.restart-api

echo   checking code...
pushd "%ROOT%\backend"
set RESTART_WATCH=0
python -c "import app.main" >nul 2>"%TEMP%\cim-restart-check.txt"
if errorlevel 1 (
  popd
  echo   ERROR: backend does not import, server NOT restarted:
  type "%TEMP%\cim-restart-check.txt"
  exit /b 1
)
popd
if not exist "%ROOT%\frontend\build\index.html" (
  echo   ERROR: frontend\build\index.html missing, server NOT restarted
  exit /b 1
)

type nul > "%FLAG%"
echo   restart requested, waiting for the server to pick it up...
for /l %%i in (1,1,15) do (
  if not exist "%FLAG%" goto picked
  ping -n 2 127.0.0.1 >nul
)
del "%FLAG%" >nul 2>&1
echo   ERROR: the server did not react in 15 s (is the "City Insight Map :3839" window running?)
exit /b 2

:picked
echo   old server stopped, waiting for the new one...
for /l %%i in (1,1,30) do (
  ping -n 2 127.0.0.1 >nul
  curl -s -o nul -f http://127.0.0.1:3839/api/auth/roles && goto ok
)
echo   WARNING: new server did not answer in 30 s, look at the "City Insight Map :3839" window
exit /b 3

:ok
echo   OK: server is back on http://127.0.0.1:3839
exit /b 0
