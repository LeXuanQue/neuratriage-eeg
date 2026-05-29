@echo off
setlocal
set APP_DIR=%~dp0
set LOCAL_PY=%APP_DIR%..\.venv\Scripts\python.exe
set EEG_PY=C:\Users\Admin\EEG\.venv\Scripts\python.exe
set PY=%LOCAL_PY%

if not exist "%PY%" set PY=python

call :check_deps
if errorlevel 1 (
  if exist "%EEG_PY%" (
    set PY=%EEG_PY%
    call :check_deps
  )
)

if errorlevel 1 (
  echo Missing pipeline dependencies. Run:
  echo   .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  exit /b 1
)

"%PY%" "%APP_DIR%app.py" --host 127.0.0.1 --port 8600
exit /b 0

:check_deps
"%PY%" -c "import numpy,pandas,scipy,sklearn,lightgbm,optuna,joblib; import PyEMD" >nul 2>nul
if errorlevel 1 (
  exit /b 1
)
exit /b 0
