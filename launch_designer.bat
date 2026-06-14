@echo off
setlocal enabledelayedexpansion
REM Mini Antenna Designer Launcher (Windows) - robust, dependency-aware
title Mini Antenna Designer
cd /d "%~dp0"

echo ================================================
echo   Mini Antenna Designer - Launcher
echo ================================================
echo.

REM --- 1. Find a working Python interpreter ----------------------------------
set "PY="
REM Prefer the py launcher (handles multiple installs), then python, then python3.
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    python3 --version >nul 2>&1 && set "PY=python3"
)
if not defined PY (
    echo ERROR: Python was not found.
    echo.
    echo Install Python 3.8 or newer from https://www.python.org/downloads/
    echo During install, tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo Using interpreter: %PY%  (%PYVER%)

REM --- 2. Use a virtual environment if present (do not require one) -----------
if defined VIRTUAL_ENV (
    echo Virtual environment active: %VIRTUAL_ENV%
) else if exist "venv\Scripts\activate.bat" (
    echo Activating venv...
    call "venv\Scripts\activate.bat"
    set "PY=python"
) else if exist ".venv\Scripts\activate.bat" (
    echo Activating .venv...
    call ".venv\Scripts\activate.bat"
    set "PY=python"
)

REM --- 3. Ensure pip exists ---------------------------------------------------
%PY% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip not found - bootstrapping with ensurepip...
    %PY% -m ensurepip --upgrade >nul 2>&1
)

REM --- 4. Check whether dependencies are already importable -------------------
echo.
echo Checking dependencies...
%PY% -c "import numpy, scipy, matplotlib, shapely, ezdxf, loguru" >nul 2>&1
if errorlevel 1 (
    echo Some dependencies are missing. Installing from requirements.txt ...
    %PY% -m pip install --upgrade pip >nul 2>&1
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency installation failed.
        echo Try running this command manually to see the error:
        echo     %PY% -m pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
) else (
    echo All core dependencies present.
)

REM --- 5. Verify the GUI toolkit (tkinter ships with python.org installers) ---
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: tkinter ^(the GUI toolkit^) is not available in this Python.
    echo The Microsoft Store build of Python often omits it.
    echo Install Python from https://www.python.org/downloads/ instead.
    echo.
    pause
    exit /b 1
)

REM --- 6. Launch --------------------------------------------------------------
echo.
echo ================================================
echo   Starting Mini Antenna Designer...
echo ================================================
echo.
%PY% main.py
set "RC=%errorlevel%"
if not "%RC%"=="0" (
    echo.
    echo Application exited with error code %RC%.
    echo See antenna_designer.log for details.
)

echo.
echo Press any key to close...
pause >nul
endlocal
