@echo off
:: Universal Local Memory (ULM) - Daily/Interval Trigger Script
echo [*] Triggering Universal Local Memory Pipeline
cd /d "%~dp0"
python main.py --parser antigravity --injector gemini_md
if %errorlevel% neq 0 (
    echo [-] ULM pipeline failed with error code %errorlevel%
    exit /b %errorlevel%
) else (
    echo [+] ULM pipeline executed successfully!
)
