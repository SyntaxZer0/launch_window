@echo off
REM Launch Window — finds Python, then starts the game (Windows).
REM Usage:  double-click, or  run.bat 42
cd /d "%~dp0"

REM Prefer the py launcher, then python on PATH.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )

if not defined PY (
    echo Launch Window needs Python 3.12 or newer.
    echo Install it from https://www.python.org/downloads/
    echo ^(tick "Add python.exe to PATH" in the installer^)
    pause
    exit /b 1
)

REM Check the version is at least 3.12.
%PY% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)" 2>nul
if errorlevel 1 (
    echo Your Python is too old:
    %PY% --version
    echo Please install Python 3.12+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

%PY% launch_window.py %*