@echo off
setlocal enabledelayedexpansion
title VeritasRAG
cd /d "%~dp0"
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

REM ============================================================
REM  VeritasRAG - single launcher.
REM  First run: installs everything automatically (10-20 min).
REM  Every run after: just starts the app at localhost:8000.
REM ============================================================

REM ---- Locate a virtual environment (.venv or venv) ----
set "VENV="
if exist "%APP_DIR%\.venv\Scripts\python.exe" set "VENV=%APP_DIR%\.venv"
if exist "%APP_DIR%\venv\Scripts\python.exe"  set "VENV=%APP_DIR%\venv"

REM ---- Decide whether first-time setup is needed ----
set "NEEDSETUP=0"
if "!VENV!"=="" set "NEEDSETUP=1"
if not "!VENV!"=="" "!VENV!\Scripts\python.exe" -c "import fastapi,uvicorn,faiss" 2>nul || set "NEEDSETUP=1"

if "!NEEDSETUP!"=="1" (
    echo.
    echo === First-time setup. This downloads packages and can take 10-20 minutes. ===
    echo.
    if "!VENV!"=="" (
        echo Creating virtual environment...
        python -m venv "%APP_DIR%\.venv"
        if errorlevel 1 (
            echo [ERROR] Python not found. Install Python 3.10-3.13 from python.org
            echo         and tick "Add Python to PATH", then run START.bat again.
            pause & exit /b 1
        )
        set "VENV=%APP_DIR%\.venv"
    )
    set "PY=!VENV!\Scripts\python.exe"
    echo Installing Python packages...
    "!PY!" -m pip install --upgrade pip
    "!PY!" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    "!PY!" -m pip install -r "%APP_DIR%\requirements.txt"
    if errorlevel 1 ( echo [ERROR] Package install failed - check internet. & pause & exit /b 1 )
    if not exist "%APP_DIR%\app\frontend\dist\index.html" (
        echo Building web frontend...
        pushd "%APP_DIR%\app\frontend"
        call npm install && call npm run build
        popd
    )
    echo Preparing configuration...
    "!PY!" "%APP_DIR%\bootstrap_env.py"
    echo Downloading AI models ^(embedding + verifier, ~260 MB, first time only^)...
    "!PY!" -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); from transformers import pipeline; pipeline('text-classification', model='cross-encoder/nli-deberta-v3-base', device=-1); print('AI models ready')"
    where ollama >nul 2>nul && ( echo Pulling offline model... & ollama pull phi4-mini ) || echo [WARN] Ollama not installed - offline mode unavailable ^(get it at ollama.com^).
    echo.
    echo === Setup complete. Starting the app... ===
)

set "PY=!VENV!\Scripts\python.exe"

REM ---- Ensure the Anthropic SDK is present (online mode via Claude) ----
"!PY!" -c "import anthropic" 2>nul || "!PY!" -m pip install anthropic

REM ---- Pre-warm the offline model so first offline query is fast ----
where ollama >nul 2>nul && start /b "" cmd /c "ollama run phi4-mini --keepalive 30m """ >nul 2>nul

REM ---- Open the browser once the server is up ----
start "" cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:8000"

echo ============================================================
echo   VeritasRAG is running at   http://localhost:8000
echo   Keep this window OPEN.  Press Ctrl+C here to stop.
echo ============================================================
"!PY!" -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
pause
