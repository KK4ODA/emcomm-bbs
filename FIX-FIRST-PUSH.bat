@echo off
setlocal
REM ===========================================================================
REM  Emcomm BBS - fix a rejected first push
REM
REM  Run this ONLY if SETUP-GITHUB.bat failed with:
REM      ! [rejected]  main -> main (fetch first)
REM
REM  Cause: the repository on GitHub was created with a README (or a .gitignore
REM  or license), so it has one auto-generated commit that your folder does not.
REM
REM  This script replaces that auto-generated commit with your real project.
REM  Safe to run once, right after creating the repo. Do NOT run it later, when
REM  GitHub holds work you actually want to keep.
REM ===========================================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   Fix rejected first push
echo ============================================================
echo.

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not on PATH.
    pause
    exit /b 1
)

REM --- Show what is currently on GitHub so you can confirm it is throwaway ---
echo Checking what is on GitHub right now...
echo.
git fetch origin main >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Could not reach https://github.com/KK4ODA/emcomm-bbs
    echo         Check that the repository exists and you are signed in.
    pause
    exit /b 1
)

echo   Commits currently on GitHub:
git --no-pager log origin/main --oneline
echo.
echo   Files currently on GitHub:
git --no-pager ls-tree -r --name-only origin/main
echo.
echo   Commits in THIS folder that will replace them:
git --no-pager log --oneline
echo.
echo ============================================================
echo   If the GitHub side above is just an auto-generated README
echo   / .gitignore / LICENSE, it is safe to overwrite.
echo ============================================================
echo.

set "OK="
set /p OK="Overwrite GitHub with this folder? (type YES to continue): "
if /i not "%OK%"=="YES" (
    echo.
    echo Cancelled. Nothing was changed.
    pause
    exit /b 0
)

echo.
echo Pushing...
git push -u origin main --force
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push still failed. Copy the message above and send it over.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS
echo ============================================================
echo.
echo   https://github.com/KK4ODA/emcomm-bbs
echo.
echo   From now on use PUSH-TO-GITHUB.bat for updates.
echo   You can delete this FIX-FIRST-PUSH.bat file - it is only
echo   needed for a first push, and using it later would erase
echo   real work on GitHub.
echo.
pause
