@echo off
setlocal
set APP_DIR=%~dp0
set PY=%APP_DIR%.venv\Scripts\python.exe
if not exist "%PY%" set PY=C:\Users\Admin\EEG\.venv\Scripts\python.exe

"%PY%" -c "import numpy,pandas,scipy,sklearn,lightgbm,optuna,joblib" >nul 2>nul
if errorlevel 1 (
  set PY=C:\Users\Admin\EEG\.venv\Scripts\python.exe
)

"%PY%" "%APP_DIR%app.py" --host 127.0.0.1 --port 8501
