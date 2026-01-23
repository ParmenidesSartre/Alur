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
echo Step 1/6: Checking git status...
git status -s | findstr /r /c:"." >nul
if %errorlevel%==0 (
    echo Error: Working directory has uncommitted changes
    git status -s
    exit /b 1
)
echo OK: Working directory clean

echo.
echo Step 2/6: Updating version numbers...

REM Update pyproject.toml
powershell -Command "(Get-Content pyproject.toml) -replace '^version = .*', 'version = \"%VERSION%\"' | Set-Content pyproject.toml"
echo OK: Updated pyproject.toml

REM Update src/alur/__init__.py
powershell -Command "(Get-Content src\alur\__init__.py) -replace '^__version__ = .*', '__version__ = \"%VERSION%\"' | Set-Content src\alur\__init__.py"
echo OK: Updated src\alur\__init__.py

REM Update README.md
powershell -Command "(Get-Content README.md) -replace '\*\*Current Version:\*\* [0-9.]+', '**Current Version:** %VERSION%' | Set-Content README.md"
echo OK: Updated README.md

echo.
echo WARNING: Update CHANGELOG.md manually
echo    Add entry for [%VERSION%]
echo.
pause

echo.
echo Step 3/6: Committing version bump...
git add pyproject.toml src\alur\__init__.py README.md CHANGELOG.md
git commit -m "chore: bump version to v%VERSION%"
echo OK: Version bump committed

echo.
echo Step 4/6: Pushing to main...
git push origin main
echo OK: Pushed to main

echo.
echo Step 5/6: Creating git tag...
git tag -a "%TAG%" -m "Release %TAG%: %DESCRIPTION%"
echo OK: Tag %TAG% created

echo.
echo Step 6/6: Pushing tag to GitHub...
git push origin "%TAG%"
echo OK: Tag pushed to GitHub

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
