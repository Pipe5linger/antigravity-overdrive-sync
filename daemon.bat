@echo off
title ULM Background Daemon
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe main.py daemon
) else (
    python main.py daemon
)
pause
