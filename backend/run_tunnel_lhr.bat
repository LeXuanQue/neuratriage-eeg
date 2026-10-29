@echo off
setlocal
set ROOT_DIR=%~dp0..
set BACKEND_DIR=%~dp0
set PY=%ROOT_DIR%\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

echo Starting NeuraTriage backend on port 8501...
start "NeuraTriage Backend" cmd /k "cd /d %BACKEND_DIR% && %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8501"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul

echo.
echo Starting localhost.run SSH tunnel...
echo The public URL will appear below (look for lhr.life):
echo.
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:127.0.0.1:8501 nokey@localhost.run
