@echo off
rem Opens the job site on this computer at http://localhost:8000 (Windows: double-click this file).
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000/"
python -m http.server 8000 --bind 127.0.0.1
