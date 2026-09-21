@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (
  echo Python 3 is required.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m playwright install chromium
echo Setup completed. Double-click Start-Dev.cmd to run the program.
pause
