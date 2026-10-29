@echo off
setlocal
set ROOT_DIR=%~dp0..
set BACKEND_DIR=%~dp0
set PY=%ROOT_DIR%\.venv\Scripts\python.exe
set CF=%ROOT_DIR%\tools\cloudflared.exe
if not exist "%PY%" set PY=python
if not exist "%CF%" (
  echo cloudflared.exe not found at tools\cloudflared.exe
  exit /b 1
)

echo Starting NeuraTriage backend on port 8501...
start "NeuraTriage Backend" cmd /k "cd /d %BACKEND_DIR% && %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8501"

echo Waiting for backend to start...
timeout /t 5 /nobreak >nul

echo.
echo Starting Cloudflare Tunnel...
echo The public URL will appear below (look for trycloudflare.com):
echo.
"%CF%" tunnel --url http://127.0.0.1:8501
