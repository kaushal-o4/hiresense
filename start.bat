@echo off
REM One-command start for HireSense: checks the prerequisites, then opens the backend and frontend in two windows.
REM First run installs everything (takes a while). Afterwards open http://localhost:5173
cd /d "%~dp0"

where py >nul 2>nul || where python >nul 2>nul || (echo ERROR: Python is not installed. Get it from https://www.python.org/downloads/ & pause & exit /b 1)
where node >nul 2>nul || (echo ERROR: Node.js is not installed. Get it from https://nodejs.org/ & pause & exit /b 1)

where ollama >nul 2>nul
if errorlevel 1 (
  echo WARNING: Ollama is not installed - AI features will show "unavailable". See README section 2.
) else (
  ollama list 2>nul | findstr /i "qwen3" >nul || (
    echo The AI model is not downloaded yet. Downloading qwen3:4b ^(about 2.5 GB, one time^)...
    ollama pull qwen3:4b
  )
)

start "HireSense backend" cmd /k "%~dp0start-backend.bat"
start "HireSense frontend" cmd /k "%~dp0start-frontend.bat"
echo.
echo Backend:  http://127.0.0.1:8000/docs
echo Frontend: http://localhost:5173  (opens when both windows say they are ready)
timeout /t 8 >nul
start "" http://localhost:5173
