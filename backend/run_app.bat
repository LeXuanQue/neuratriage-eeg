@echo off
setlocal
set APP_DIR=%~dp0
set ROOT_DIR=%APP_DIR%..
set PY=%ROOT_DIR%\.venv\Scripts\python.exe

if not exist "%PY%" set PY=python

"%PY%" -c "import fastapi,uvicorn,sqlalchemy,pydantic_settings,apscheduler,bcrypt,jwt,numpy,scipy,pandas,sklearn,lightgbm,joblib,multipart,reportlab" >nul 2>nul
if errorlevel 1 (
  echo Missing FastAPI app dependencies. Run:
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

if "%PORT%"=="" set PORT=8501

pushd "%ROOT_DIR%\backend"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
popd
