@echo off
setlocal
title AV Agent

REM locate Python (py launcher first, then python)
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python not found. Please run install.bat first.
  pause
  exit /b 1
)

echo Starting AV Agent...
echo Closing this window will minimize the app to the system tray.
%PY% -m desktop.main
if errorlevel 1 (
  echo.
  echo Startup failed. Make sure you ran install.bat first.
  pause
)
