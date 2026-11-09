@echo off
title Debolat AI - build installer
cd /d "%~dp0"
echo.
echo ============================================================
echo   Debolat AI - building the Windows installer
echo   Folder: %CD%
echo ============================================================

echo.
echo [check] Looking for Node.js...
where node >nul 2>nul
if errorlevel 1 goto nonode
where npm >nul 2>nul
if errorlevel 1 goto nonode

echo [check] Looking for the Python environment...
if not exist ".venv\Scripts\python.exe" goto novenv

echo.
echo === 1/4  Installing Python packages ===
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto fail

echo.
echo === 2/4  Compiling the Python backend into backend.exe ===
if exist build-backend rmdir /s /q build-backend
if exist dist-backend rmdir /s /q dist-backend
".venv\Scripts\python.exe" -m PyInstaller backend.spec --noconfirm --distpath dist-backend --workpath build-backend
if errorlevel 1 goto fail
if not exist "dist-backend\backend\backend.exe" goto fail
echo backend.exe was created.

echo.
echo === 3/4  Installing Node packages ===
call npm install
if errorlevel 1 goto fail

echo.
echo === 4/4  Building the installer ===
call npm run dist
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE. Your installer is in the "release" folder:
dir /b release\*.exe
echo ============================================================
pause
exit /b 0

:nonode
echo.
echo *** Node.js was not found. ***
echo Install it from https://nodejs.org  (choose the LTS version),
echo then close this window and run build.bat again.
pause
exit /b 1

:novenv
echo.
echo *** The .venv folder was not found in this folder. ***
echo Open a terminal here and run these three lines, then run build.bat again:
echo     python -m venv .venv
echo     .venv\Scripts\activate
echo     pip install -r requirements.txt
pause
exit /b 1

:fail
echo.
echo *** Build failed. Scroll up to the FIRST red or "error" line - that is the cause. ***
pause
exit /b 1
