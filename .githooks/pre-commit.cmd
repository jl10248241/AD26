@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\dupbasename_guard.ps1"
if errorlevel 1 exit /b 1
python ".\tools\dupbasename_guard.py"
exit /b %ERRORLEVEL%
