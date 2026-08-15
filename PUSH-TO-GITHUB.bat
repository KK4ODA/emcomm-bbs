@echo off
REM ===========================================================================
REM  Emcomm BBS - push local changes to GitHub
REM
REM  Double-click this after you have edited files in this folder.
REM  It stages everything, commits, and pushes to
REM  https://github.com/KK4ODA/emcomm-bbs
REM
REM  Requires Git for Windows:  https://git-scm.com/download/win
REM ===========================================================================

cd /d "%~dp0"

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not on PATH.
    echo Install Git for Windows from https://git-scm.com/download/win
    pause
    exit /b 1
)

echo.
echo ===========================================================
echo  Changes to be pushed
echo ===========================================================
git status --short
echo.

git diff --quiet && git diff --cached --quiet
if %errorlevel% equ 0 (
    echo Nothing has changed since the last commit.
    echo.
    echo Pushing any commits that have not reached GitHub yet...
    git push
    pause
    exit /b 0
)

set "MSG="
set /p MSG="Describe this change (press Enter for a dated default): "
if "%MSG%"=="" set "MSG=Update %DATE% %TIME%"

git add -A
git commit -m "%MSG%"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Commit failed. See the message above.
    pause
    exit /b 1
)

echo.
echo Pushing to GitHub...
git push
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed.
    echo   - If this is your first push, a browser window may open to sign in.
    echo   - If someone changed the repo on GitHub, run PULL-FROM-GITHUB.bat first.
    pause
    exit /b 1
)

echo.
echo ===========================================================
echo  Done. View it at https://github.com/KK4ODA/emcomm-bbs
echo ===========================================================
pause
