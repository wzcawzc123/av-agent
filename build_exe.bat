@echo off
setlocal enabledelayedexpansion
title AV Agent - one-click build

echo ==========================================
echo   AV Agent one-click build (Windows)
echo ==========================================
echo.

REM ---------- locate Python ----------
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found. Run install.bat first.
  pause
  exit /b 1
)

echo [1/4] Python: %PY%

echo [2/4] Installing dependencies...
%PY% -m pip install -r requirements.txt >nul 2>&1
if not errorlevel 1 goto :deps_ok
echo       Retrying with Tsinghua mirror (user install)...
%PY% -m pip install --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
if errorlevel 1 goto :error

:deps_ok
%PY% -m pip install pyinstaller >nul 2>&1
if not errorlevel 1 goto :pyi_ok
%PY% -m pip install --user pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
if errorlevel 1 goto :error

:pyi_ok
echo.
echo [3/4] Building with PyInstaller (3-8 min, PySide6 is large)...
%PY% -m PyInstaller --clean --noconfirm av-agent.spec
if errorlevel 1 goto :error

echo.
echo [4/4] Done!
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
