@echo off
REM  Multi-Agent RAG — launcher (assumes .venv is already activated)
REM
REM  URLs:
REM    Frontend  http://localhost:5173
REM    Backend   http://localhost:8000
REM    API docs  http://localhost:8000/docs
REM
REM  Models:  online = Groq (Llama 4 Scout 17B, needs GROQ_API_KEY in .env)
REM           offline = Ollama (Phi-3 mini) — start it separately:
REM                     ollama pull phi3:mini  &&  ollama serve
setlocal
cd /d "%~dp0"

echo.
echo  ================================================================
echo   Multi-Agent RAG  -  starting servers
echo  ================================================================
echo.

REM --- first-run: ensure a .env exists (cloud mode needs GROQ_API_KEY) ---
if not exist ".env" (
  echo  [setup] No .env found - creating one from .env.example
  copy /y ".env.example" ".env" >nul
  echo  [setup] Edit .env and set GROQ_API_KEY before using cloud mode.
)

REM --- backend ---
echo  [backend]  http://localhost:8000
echo  [api docs] http://localhost:8000/docs
start "RAG backend" cmd /k "cd /d %~dp0 && uvicorn app.backend.main:app --reload --port 8000"

timeout /t 2 /nobreak >nul

REM --- frontend (npm install on first run if node_modules is missing) ---
echo  [frontend] http://localhost:5173
start "RAG frontend" cmd /k "cd /d %~dp0\app\frontend && (if not exist node_modules npm install) && npm run dev"

echo.
echo  ================================================================
echo   Open in browser:  http://localhost:5173
echo   Offline mode? Start Ollama:  ollama pull phi3:mini  ^&^&  ollama serve
echo   Close both windows to stop.
echo  ================================================================
echo.
pause
endlocal
