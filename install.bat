@echo off
setlocal enabledelayedexpansion
title AV Agent - installer
echo ==========================================
echo   AV Agent one-click installer (Windows)
echo ==========================================
echo.

REM ========== 1. locate Python (py launcher first, then python) ==========
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto :no_python

REM ========== 2. verify version >= 3.12 ==========
set "VER="
for /f "usebackq tokens=2 delims= " %%v in (`"%PY%" --version 2^>^&1`) do set "VER=%%v"
if not defined VER goto :no_python
for /f "tokens=1,2 delims=." %%a in ("%VER%") do set "VMAJ=%%a" & set "VMIN=%%b"
set /a VNUM=0
if defined VMAJ if defined VMIN set /a VNUM=VMAJ*100+VMIN
echo [1/4] Python found: %VER%
if %VNUM% LSS 312 (
  echo.
  echo [WARN] AV Agent needs Python 3.12 or newer.
  echo        Install it from https://www.python.org/downloads/
  echo        (tick "Add python.exe to PATH"), then re-run this script.
  pause
  exit /b 1
)
echo.

REM ========== 3. upgrade pip (best effort) ==========
echo [2/4] Upgrading pip...
%PY% -m pip install --upgrade pip >nul 2>&1

REM ========== 4. install dependencies with automatic fallbacks ==========
echo [3/4] Installing dependencies. PySide6 is large, this may take a few minutes.
echo       Trying official PyPI first, then mirrors automatically...
echo.

%PY% -m pip install -r requirements.txt >nul 2>&1
if not errorlevel 1 goto :deps_ok

echo [RETRY 1/2] Official PyPI failed. Trying user install...
%PY% -m pip install --user -r requirements.txt >nul 2>&1
if not errorlevel 1 goto :deps_ok

echo [RETRY 2/2] Trying Tsinghua mirror (user install)...
%PY% -m pip install --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
if not errorlevel 1 goto :deps_ok

goto :deps_fail

:deps_ok
echo.
echo [4/4] Verifying imports...
%PY% -c "import fastapi, PySide6, uvicorn; print('  All core imports OK.')"
echo.
echo ==========================================
echo   Installation complete!
echo.
echo   Start the app:    double-click run.bat
echo   (or type:  %PY% -m desktop.main)
echo   Build exe:        double-click build_exe.bat
echo ==========================================
pause
exit /b 0

:no_python
echo [ERROR] Python 3.12+ was not found on this system.
echo   - Install from https://www.python.org/downloads/
echo     IMPORTANT: tick "Add python.exe to PATH" during install
echo   - Or install from Microsoft Store (search "Python 3.12")
echo   Then re-run this script.
pause
exit /b 1

:deps_fail
echo [ERROR] Failed to install dependencies after all retries.
echo   Possible causes: no network, firewall, or corporate proxy.
echo   You can retry manually with:
echo     %PY% -m pip install --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pause
exit /b 1
