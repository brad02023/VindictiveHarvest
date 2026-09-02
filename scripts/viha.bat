@echo off
cd /d "%~dp0.."
if exist "%~dp0..\.venv\Scripts\pythonw.exe" (
  start "" "%~dp0..\.venv\Scripts\pythonw.exe" -m viha
  goto :eof
)
if exist "%~dp0..\.venv\Scripts\python.exe" (
  "%~dp0..\.venv\Scripts\python.exe" -m viha
  goto :eof
)
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" pythonw -m viha
) else (
  python -m viha
)
