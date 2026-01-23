@echo off
REM Quick release script for Alur Framework (Windows)
REM Usage: scripts\release.bat 0.8.0 "Silver Layer Support"

setlocal enabledelayedexpansion

if "%~1"=="" (
    echo Error: Missing version argument
    echo Usage: scripts\release.bat ^<version^> ^<description^>
    echo Example: scripts\release.bat 0.8.0 "Silver Layer Support"
    exit /b 1
)

if "%~2"=="" (
    echo Error: Missing description argument
    echo Usage: scripts\release.bat ^<version^> ^<description^>
    echo Example: scripts\release.bat 0.8.0 "Silver Layer Support"
    exit /b 1
)

set VERSION=%~1
set DESCRIPTION=%~2
set TAG=v%VERSION%

echo ====================================
echo Alur Framework Release Script
echo ====================================
echo.
echo Version: %VERSION%
echo Tag: %TAG%
echo Description: %DESCRIPTION%
echo.

set /p CONFIRM="Continue with release? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Release cancelled
    exit /b 1
)

echo.
echo Step 1/5: Checking git status...
git status -s | findstr /r /c:"." >nul
if %errorlevel%==0 (
    echo Error: Working directory has uncommitted changes
    git status -s
    exit /b 1
)
echo OK: Working directory clean

echo.
echo Step 2/5: Bumping version numbers...
python scripts\bump_version.py %VERSION%
if %errorlevel% neq 0 (
    echo Error: Version bump failed
    exit /b 1
)

echo.
echo Step 3/5: Committing version bump...
git add .
git commit -m "chore: bump version to v%VERSION%"
if %errorlevel% neq 0 (
    echo Error: Commit failed
    exit /b 1
)
echo OK: Version bump committed

echo.
echo Step 4/5: Pushing to main...
git push origin main
if %errorlevel% neq 0 (
    echo Error: Push failed
    exit /b 1
)
echo OK: Pushed to main

echo.
echo Step 5/5: Creating and pushing tag...
git tag -a "%TAG%" -m "Release %TAG%: %DESCRIPTION%"
git push origin "%TAG%"
if %errorlevel% neq 0 (
    echo Error: Tag push failed
    exit /b 1
)
echo OK: Tag %TAG% pushed to GitHub

echo.
echo ====================================
echo Release %TAG% initiated!
echo ====================================
echo.
echo Next steps:
echo 1. Monitor GitHub Actions: https://github.com/ParmenidesSartre/Alur/actions
echo 2. Verify PyPI: https://pypi.org/project/alur-framework/%VERSION%/
echo 3. Create GitHub Release: https://github.com/ParmenidesSartre/Alur/releases/new?tag=%TAG%
echo.
echo GitHub Actions will automatically build and publish to PyPI.
echo.

endlocal
