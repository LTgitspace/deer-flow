@echo off
title UniDeer - Frontend
cd /d "%~dp0"

echo ========================================
echo  Starting UniDeer Frontend...
echo ========================================
echo.

:: Kill any existing frontend instance (only the frontend window)
taskkill /fi "WindowTitle eq UniDeer - Frontend*" /f >nul 2>&1
timeout /t 1 /nobreak >nul

:: Start Frontend
echo Building and starting Frontend on port 3000...
start "UniDeer - Frontend" cmd /k "cd /d "%~dp0frontend" && set BETTER_AUTH_SECRET=local-dev-secret && pnpm build && pnpm start"

echo.
echo ========================================
echo  Frontend starting...
echo  Frontend: http://localhost:3000
echo  Close the "UniDeer - Frontend" window to stop it.
echo ========================================
echo.
