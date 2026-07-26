@echo off
title DeerFlow
cd /d "%~dp0"

echo ========================================
echo  Starting DeerFlow...
echo ========================================
echo.

:: Kill any existing instances
taskkill /fi "WindowTitle eq DeerFlow - Backend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq DeerFlow - Frontend*" /f >nul 2>&1
timeout /t 1 /nobreak >nul

:: Start Backend Gateway
echo [1/2] Starting Gateway on port 8001...
start "DeerFlow - Backend" cmd /c "cd /d "%~dp0backend" && set DEER_FLOW_AUTH_DISABLED=1 && uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"

:: Wait for backend to initialize
timeout /t 5 /nobreak >nul

:: Start Frontend
echo [2/2] Starting Frontend on port 3000...
start "DeerFlow - Frontend" cmd /c "cd /d "%~dp0frontend" && set BETTER_AUTH_SECRET=local-dev-secret && pnpm dev"

echo.
echo ========================================
echo  DeerFlow started!
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:3000
echo.
echo  Close this window to see stop instructions.
echo ========================================
echo.

:: Wait for user to press a key to stop
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping services...
taskkill /fi "WindowTitle eq DeerFlow - Backend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq DeerFlow - Frontend*" /f >nul 2>&1
echo Done.
timeout /t 2 /nobreak >nul
