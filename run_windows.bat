@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Install Node.js LTS from https://nodejs.org/
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js LTS with npm enabled.
  pause
  exit /b 1
)

echo Installing/updating dependencies...
call npm install --include=dev
if errorlevel 1 pause & exit /b 1

echo Starting OrionSSH in development mode...
call npm run dev
pause
