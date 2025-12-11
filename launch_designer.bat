@echo off
REM Mini Antenna Designer Launcher (Windows)
echo ================================================
echo   Mini Antenna Designer - Professional Launcher
echo ================================================
echo.

REM Check if we're in a virtual environment
if defined VIRTUAL_ENV (
    echo Using virtual environment: %VIRTUAL_ENV%
) else (
    REM Try to find and activate venv
    if exist "venv\Scripts\activate.bat" (
        echo Found virtual environment at venv\Scripts\activate.bat
        call venv\Scripts\activate.bat
    ) else if exist "env\Scripts\activate.bat" (
        echo Found virtual environment at env\Scripts\activate.bat
        call env\Scripts\activate.bat
    ) else (
        echo WARNING: No virtual environment found. Installing dependencies globally...
    )
)

echo.
echo Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and ensure it's in your PATH
    pause
    exit /b 1
)

echo.
echo Installing/updating dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo WARNING: Some dependencies may have failed to install
    echo Trying to continue anyway...
)

echo.
echo Running pre-launch validation tests...
python validate.py
if errorlevel 1 (
    echo WARNING: Validation tests failed. The application may not work correctly.
    choice /m "Continue anyway?"
    if errorlevel 2 (
        echo Launch cancelled by user.
        exit /b 1
    )
)

echo.
echo ================================================
echo   Starting Mini Antenna Designer...
echo ================================================
echo Close this window to stop the application
echo.

python main.py
if errorlevel 1 (
    echo.
    echo Application exited with error code %errorlevel%
    echo Check antenna_designer.log for detailed error information
)

echo.
echo Press any key to exit...
pause >nul
