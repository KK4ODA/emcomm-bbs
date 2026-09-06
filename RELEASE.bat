@echo off
setlocal
:: Cut a release:  RELEASE.bat 1.7.0
:: Sets the version in version.py, runs the tests, commits, tags v1.7.0, pushes,
:: and creates the GitHub release with the matching CHANGELOG section as notes.
:: GitHub Actions (.github\workflows\release.yml) then builds the Windows
:: installer and portable zip and attaches them to that release.
::
:: Needs: git, the GitHub CLI (gh, signed in), and a "## [1.7.0]" section in CHANGELOG.md.
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: RELEASE.bat ^<version^>     e.g. RELEASE.bat 1.7.0
    exit /b 1
)
set VER=%~1
git diff --quiet || (echo Working tree has uncommitted changes. Commit or stash them first. & exit /b 1)
python packaging\release_notes.py %VER% > "%TEMP%\emcomm_release_notes.md" || (echo Add a "## [%VER%]" section to CHANGELOG.md first. & exit /b 1)
python -c "import re,pathlib;p=pathlib.Path('version.py');s=p.read_text(encoding='utf-8');n=re.sub(r'__version__ = \"[^\"]+\"','__version__ = \"%VER%\"',s);p.write_text(n,encoding='utf-8');print('version.py ->','%VER%')" || exit /b 1
python -m unittest discover -s tests || (echo Tests failed; release aborted. & git checkout -- version.py & exit /b 1)
git add version.py
git commit -m "Release v%VER%" || exit /b 1
git tag -a "v%VER%" -m "Emcomm BBS v%VER%" || exit /b 1
git push origin main --follow-tags || exit /b 1
gh release create "v%VER%" --title "Emcomm BBS %VER%" --latest --notes-file "%TEMP%\emcomm_release_notes.md" || exit /b 1
echo.
echo Released v%VER%. The installer build is running at:
echo   https://github.com/KK4ODA/emcomm-bbs/actions
echo Assets appear on:
echo   https://github.com/KK4ODA/emcomm-bbs/releases/tag/v%VER%
endlocal
