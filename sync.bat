@echo off
:: Universal Local Memory (ULM) - Interactive Setup & Trigger Script
:: Optimized for Windows PowerShell integration and user-centric configuration

title ULM Persona Sync Control Console

echo ======================================================================
echo          VESPERA CALIGO - UNIVERSAL LOCAL MEMORY CONTROL
echo ======================================================================
echo [*] Initializing workspace verification...

:: Resolve current script execution directory
cd /d "%~dp0"

:: 1. Detect Python Executable
where python >nul 2>nul
if %errorlevel% neq 0 (
    :: Try standard user-level Windows Python installations
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" (
        set PYTHON_EXE="%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe"
    ) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
        set PYTHON_EXE="%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
    ) else (
        echo [ERROR] Python not found in system PATH or standard folders.
        echo please install Python 3.11+ or add it to system PATH variables.
        pause
        exit /b 1
    )
) else (
    set PYTHON_EXE=python
)

:: 2. Auto-Detect Google Drive Desktop Sync folders
echo [*] Detecting filesystem mirrors...
if exist "G:\My Drive" (
    echo [+] Located Google Drive Client mount point: G:\My Drive
) else if exist "%USERPROFILE%\Google Drive\My Drive" (
    echo [+] Located Google Drive Client folder: %USERPROFILE%\Google Drive\My Drive
) else (
    echo [!] Google Drive mount not found in default G:\ drive or User profile directory.
    echo     Verify if Google Drive for Desktop client is running.
)

:: 3. Sync Execution Prompt
echo.
set /p CHOICE="[?] Initiate dynamic context-bridge sync run? (Y/N): "
if /i "%CHOICE%" neq "Y" (
    echo [*] Synchronization aborted by user request.
    pause
    exit /b 0
)

echo.
echo ======================================================================
echo 🚀 EXECUTING ULM DYNAMIC MEMORY SYNCHRONIZATION PIPELINE
echo ======================================================================

:: Trigger python script
%PYTHON_EXE% main.py --parser antigravity --injector gemini_md

if %errorlevel% neq 0 (
    echo.
    echo [-] ULM pipeline execution failed with exit code %errorlevel%
    echo ======================================================================
    pause
    exit /b %errorlevel%
) else (
    echo.
    echo ======================================================================
    echo [+] ULM pipeline successfully completed execution.
    echo.
    echo > [!IMPORTANT]
    echo   Active browser sessions (Gems / Chat tabs) will NOT reload dynamically.
    echo   You MUST refresh your browser window or start a new prompt thread
    echo   for cloud-hosted instances to parse the updated chatlog.yaml context.
    echo.
    echo ======================================================================
)

pause
