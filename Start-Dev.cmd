@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment is missing. Run Setup-Dev.cmd first.
  pause
  exit /b 1
)
start "" /b ".venv\Scripts\pythonw.exe" desktop_app.py
exit /b 0
