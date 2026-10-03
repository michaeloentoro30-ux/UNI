@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo UniScout - Full OpenAlex Startup
echo ================================================

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo Starting UniScout. app.py will automatically import OpenAlex data if needed.
echo.
%PYTHON% app.py
pause
