@echo off
setlocal
set "ROOT=%~dp0"
call "%ROOT%updater\UpdateAgent.exe" --check "%ROOT%updater\updater-config.json"
for %%F in ("%ROOT%app\*.exe") do (
    if exist "%%~fF" start "" "%%~fF"
    if exist "%%~fF" exit /b 0
)
exit /b 2
