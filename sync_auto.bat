@echo off
:: Universal Local Memory (ULM) - Non-Interactive Automated Sync Script
:: Perfect for Task Scheduler, automated git hooks, or quick manual double-click testing.

title ULM Automatic Sync Executor

echo ======================================================================
echo 🚀 EXECUTING ULM PIPELINE (AUTOMATIC MODE)
echo ======================================================================

cd /d "%~dp0"

:: Detect Python
set PYTHON_EXE=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" (
        set PYTHON_EXE="%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe"
    ) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
        set PYTHON_EXE="%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
    ) else (
        echo [ERROR] Python not found. Cannot run sync.
        exit /b 1
    )
)

:: Run pipeline non-interactively
%PYTHON_EXE% main.py --parser antigravity --injector gemini_md --backup

if %errorlevel% neq 0 (
    echo [ERROR] ULM sync pipeline failed with exit code %errorlevel%
    exit /b %errorlevel%
)

echo [+] ULM Sync pipeline completed successfully.
exit /b 0
