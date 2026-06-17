@echo off
title ULM Dashboard
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe main.py tui
) else (
    python main.py tui
)
pause
