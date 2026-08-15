@echo off
setlocal
REM ===========================================================================
REM  Emcomm BBS - ONE-TIME GitHub setup
REM
REM  BEFORE running this:
REM    1. Install Git for Windows:  https://git-scm.com/download/win
REM       (accept all defaults - the Credential Manager it installs is what
REM        remembers your GitHub login)
REM    2. Go to  https://github.com/new  and create a repository named
REM       exactly:   emcomm-bbs
REM       - Owner: KK4ODA
REM       - Visibility: PUBLIC
REM       - Do NOT tick "Add a README", ".gitignore", or "license".
REM         Leave the new repo completely empty. This folder already has
REM         all of that.
REM
REM  Then double-click this file. After it succeeds you never need it again -
REM  use PUSH-TO-GITHUB.bat for day-to-day updates.
REM ===========================================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   Emcomm BBS  -  first-time GitHub setup
echo ============================================================
echo.

REM --- 1. Git present? -------------------------------------------------------
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed, or not on your PATH.
    echo.
    echo   Install it from  https://git-scm.com/download/win
    echo   then close this window and run this file again.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('git --version') do echo   [OK] %%v

REM --- 2. Clear stale lock files --------------------------------------------
REM  The repository was prepared on another machine; a few zero-byte .lock
REM  files can be left behind. Git refuses to run while they exist.
if exist ".git\HEAD.lock"            del /f /q ".git\HEAD.lock"            >nul 2>&1
if exist ".git\index.lock"           del /f /q ".git\index.lock"           >nul 2>&1
if exist ".git\packed-refs.lock"     del /f /q ".git\packed-refs.lock"     >nul 2>&1
if exist ".git\config.lock"          del /f /q ".git\config.lock"          >nul 2>&1
if exist ".git\writetest"            del /f /q ".git\writetest"            >nul 2>&1
del /f /q ".git\refs\heads\*.lock" >nul 2>&1
del /f /q ".git\refs\remotes\origin\*.lock" >nul 2>&1
echo   [OK] Cleared any stale lock files

REM --- 3. Sanity-check the repository ----------------------------------------
git rev-parse --git-dir >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] This folder does not contain a valid Git repository.
    echo         Re-extract emcomm-bbs.zip and try again.
    pause
    exit /b 1
)
echo   [OK] Repository looks healthy

REM --- 4. Identity -----------------------------------------------------------
git config user.name  >nul 2>&1 || git config user.name  "KK4ODA"
git config user.email >nul 2>&1 || git config user.email "273351553+KK4ODA@users.noreply.github.com"

REM --- 5. Branch and remote --------------------------------------------------
git symbolic-ref -q HEAD refs/heads/main >nul 2>&1
git remote remove origin >nul 2>&1
git remote add origin https://github.com/KK4ODA/emcomm-bbs.git
echo   [OK] Remote set to https://github.com/KK4ODA/emcomm-bbs.git

REM --- 6. Pick up anything that changed since packaging ----------------------
git add -A >nul 2>&1
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -q -m "Add one-time GitHub setup launcher and any local adjustments"
    echo   [OK] Committed local changes
) else (
    echo   [OK] Working tree already matches the initial commit
)

REM --- 7. Push ---------------------------------------------------------------
echo.
echo Pushing to GitHub...
echo (A browser window may open asking you to sign in to GitHub. Approve it.)
echo.
git push -u origin main
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo   PUSH FAILED
    echo ============================================================
    echo.
    echo Most likely causes:
    echo.
    echo   * The repository does not exist yet on GitHub.
    echo     Create it at https://github.com/new  named  emcomm-bbs
    echo     owned by KK4ODA, PUBLIC, with NO README/gitignore/license.
    echo.
    echo   * The repository was created WITH a README. In that case run:
    echo         git push -u origin main --force
    echo     from this folder ^(safe here - the GitHub copy is empty^).
    echo.
    echo   * Sign-in was cancelled. Just run this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS
echo ============================================================
echo.
echo   Your repository is live at:
echo       https://github.com/KK4ODA/emcomm-bbs
echo.
echo   From now on, to publish changes just double-click:
echo       PUSH-TO-GITHUB.bat
echo.
pause
