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

echo Building renderer...
call npx vite build
if errorlevel 1 pause & exit /b 1

echo Building Windows package...
call npx electron-builder --win nsis portable
if errorlevel 1 pause & exit /b 1

echo.
echo Done. Check the release folder.
pause
