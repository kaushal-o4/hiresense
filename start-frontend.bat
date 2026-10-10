@echo off
REM Starts the HireSense web app on http://localhost:5173
cd /d "%~dp0frontend"
if not exist node_modules call npm install
call npm run dev
