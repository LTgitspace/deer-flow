@echo off
title UniDeer
cd /d "%~dp0"

echo ========================================
echo  Starting UniDeer...
echo ========================================
echo.

:: GitHub Token Check
if "%GITHUB_TOKEN%"=="" (
    echo WARNING: GITHUB_TOKEN is not set. GitHub MCP tools will not authenticate.
    echo Set it with: set GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    echo.
) else (
    echo GitHub token detected.
    echo.
)

:: Kill any existing instances
taskkill /fi "WindowTitle eq UniDeer - Backend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq UniDeer - Frontend*" /f >nul 2>&1
timeout /t 1 /nobreak >nul

:: Start Backend Gateway
echo [2/4] Starting Gateway on port 8001...
start "UniDeer - Backend" cmd /c "cd /d "%~dp0backend" && set DEER_FLOW_AUTH_DISABLED=1 && set GITHUB_TOKEN=%GITHUB_TOKEN% && uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"

:: Wait for backend to initialize
timeout /t 5 /nobreak >nul

:: Start Frontend
echo [3/4] Starting Frontend on port 3000...
start "UniDeer - Frontend" cmd /c "cd /d "%~dp0frontend" && set BETTER_AUTH_SECRET=local-dev-secret && pnpm build && pnpm start"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  UniDeer started!
echo  Backend:  http://localhost:8001
echo  Frontend: http://localhost:3000
echo  9Router:  http://localhost:20128
echo.
echo  Close this window to see stop instructions.
echo ========================================
echo.

:: Wait for user to press a key to stop
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping services...
taskkill /fi "WindowTitle eq UniDeer - Backend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq UniDeer - Frontend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq 9Router*" /f >nul 2>&1
echo Done.
timeout /t 2 /nobreak >nul
