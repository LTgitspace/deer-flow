@echo off
title UniDeer - Backend
cd /d "%~dp0"

echo ========================================
echo  Starting UniDeer Backend (Gateway)...
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

:: Kill any existing backend instance (only the backend window)
taskkill /fi "WindowTitle eq UniDeer - Backend*" /f >nul 2>&1
timeout /t 1 /nobreak >nul

:: Start Backend Gateway
echo Starting Gateway on port 8001...
start "UniDeer - Backend" cmd /k "cd /d "%~dp0backend" && set DEER_FLOW_AUTH_DISABLED=1 && set GITHUB_TOKEN=%GITHUB_TOKEN% && uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"

echo.
echo ========================================
echo  Backend starting...
echo  Gateway: http://localhost:8001
echo  Close the "UniDeer - Backend" window to stop it.
echo ========================================
echo.
