@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
if errorlevel 1 (
  echo.
  echo Install failed. If Python is missing, install 3.10+ from https://www.python.org/downloads/
  pause
  exit /b 1
)
echo.
pause
