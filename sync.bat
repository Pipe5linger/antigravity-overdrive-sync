@echo off
echo [*] Triggering Antigravity Overdrive Sync Pipeline...
cd /d "%~dp0"
python main.py --parser antigravity --injector gemini_md --manual
if %errorlevel% neq 0 (
    echo [-] Overdrive Sync Pipeline failed with error code %errorlevel%
) else (
    echo [+] Overdrive Sync Pipeline executed successfully
)
