@echo off
REM ===========================================================================
REM  Emcomm BBS - Windows launcher
REM  Checks Python, installs anything missing from requirements.txt, and
REM  starts the application.
REM ===========================================================================
cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.8 or newer from https://www.python.org/downloads/
    echo and tick "Add Python to PATH" during setup.
    pause
    exit /b 1
)

python -c "import requests, watchdog" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies from requirements.txt ...
    python -m pip install --quiet -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [WARNING] Could not install every dependency. Try manually:
        echo     python -m pip install -r requirements.txt
        echo.
        pause
    )
)

echo Starting Emcomm BBS...
python emcomm_bbs.py
if %errorlevel% neq 0 (
    echo.
    echo Emcomm BBS exited with an error ^(code %errorlevel%^). See the message above.
    pause
)
