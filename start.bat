@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"

echo.
echo   * Offinity_AI
echo   -----------------

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   [!!] Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Install deps if needed
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo   [>>] Installing dependencies...
    python -m pip install -r requirements.txt -q
)

:: Install Flask for web mode
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    python -m pip install flask -q
)

:: Create .env if missing
if not exist .env (
    if exist .env.example (
        echo   [>>] Creating .env from template...
        copy .env.example .env >nul
        echo   [i]  Edit .env to configure your LLM provider
    )
)

echo.

:: Check args for web mode
echo %* | find "--web" >nul
if not errorlevel 1 (
    echo   [Web] Starting Web UI...
    python main.py --web
    goto end
)

echo %* | find "-w" >nul
if not errorlevel 1 (
    python main.py --web
    goto end
)

python main.py %*

:end
pause
