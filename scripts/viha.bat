@echo off
cd /d "%~dp0.."
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" pythonw -m viha
) else (
  python -m viha
)
