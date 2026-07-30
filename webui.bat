@echo off
title Vespera ULM WebUI Launcher
cd /d "%~dp0"
echo ======================================================================
echo 🔮 LAUNCHING VESPERA ULM WEBUI CONTROL CENTER (PORT 8890)
echo ======================================================================

start http://localhost:8890

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" main.py webui
) else if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe main.py webui
) else (
    python main.py webui
)
pause
