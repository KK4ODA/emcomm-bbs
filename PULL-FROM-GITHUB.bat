@echo off
REM ===========================================================================
REM  Emcomm BBS - pull the latest version from GitHub into this folder
REM
REM  Run this if you edited files on github.com, or on another computer,
REM  and want those changes here.
REM ===========================================================================

cd /d "%~dp0"

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not on PATH.
    echo Install Git for Windows from https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Fetching from GitHub...
git pull --rebase
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Pull failed. You may have local edits that conflict.
    echo Run "git status" in this folder to see what needs attention.
    pause
    exit /b 1
)

echo.
echo Up to date.
pause
