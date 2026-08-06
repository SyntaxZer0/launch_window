@echo off
REM Launch Window (Windows) — starts the GUI; falls back to the classic version.
REM Usage:  double-click, or  run.bat 42   ·   run.bat --classic  for the old UI.
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :nopython

%PY% -c "import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,12) else 1)" 2>nul
if errorlevel 1 goto :oldpython

if /I "%~1"=="--classic" (
    %PY% launch_window.py %*
    goto :eof
)

%PY% -c "import textual" >nul 2>nul
if not errorlevel 1 goto :rungui

echo.
echo The new GUI needs the 'textual' package, which isn't installed.
set /p "ANS=Install it now with pip? [Y/n] "
if /I "%ANS%"=="n" goto :classicfallback
%PY% -m pip3 install textual
%PY% -c "import textual" >nul 2>nul
if errorlevel 1 goto :classicfallback

:rungui
%PY% tui.py %*
goto :eof

:classicfallback
echo Starting the classic terminal version instead.
%PY% launch_window.py %*
goto :eof

:nopython
echo Launch Window needs Python 3.12 or newer.
echo Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" in the installer)
pause
exit /b 1

:oldpython
echo Your Python is too old:
%PY% --version
echo Please install Python 3.12+ from https://www.python.org/downloads/
pause
exit /b 1