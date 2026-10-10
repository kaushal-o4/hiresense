@echo off
REM Starts the HireSense API on http://127.0.0.1:8000 (docs at /docs)
cd /d "%~dp0backend"
if not exist venv (
  echo Creating Python environment...
  py -3.14 -m venv venv || py -m venv venv
  venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  venv\Scripts\python.exe -m pip install -r requirements.txt
  venv\Scripts\python.exe -m pip install --no-deps kokoro==0.7.16
)
where ollama >nul 2>nul || echo WARNING: Ollama is not installed - AI features will be unavailable. See README section 2.
if not exist .env copy .env.example .env
venv\Scripts\alembic.exe upgrade head
venv\Scripts\python.exe -m app.seed --demo
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
