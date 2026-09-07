@echo off
setlocal enabledelayedexpansion
title AV Agent one-click build

echo ==========================================
echo   AV Agent one-click build (Windows)
echo ==========================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 goto :error
pip install pyinstaller
if errorlevel 1 goto :error

echo.
echo [2/3] Building with PyInstaller (3-8 min, PySide6 is large)...
pyinstaller --clean --noconfirm av-agent.spec
if errorlevel 1 goto :error

echo.
echo [3/3] Done!
echo ------------------------------------------
echo   Output: dist\AVAgent.exe
echo   Usage: send AVAgent.exe to users; double-click
echo   to open the native desktop workbench. The
echo   FastAPI service runs in the background, so
echo   phones can access it over LAN.
echo ------------------------------------------
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Check the error messages above.
pause
exit /b 1
