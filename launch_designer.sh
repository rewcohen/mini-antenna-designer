#!/bin/bash

# Mini Antenna Designer Launcher (Unix/Linux/Mac)
echo "================================================"
echo "  Mini Antenna Designer - Professional Launcher"
echo "================================================"
echo ""

# Check if we're in a virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Using virtual environment: $VIRTUAL_ENV"
else
    # Try to find and activate venv
    if [ -f "venv/bin/activate" ]; then
        echo "Found virtual environment at venv/bin/activate"
        source venv/bin/activate
    elif [ -f "env/bin/activate" ]; then
        echo "Found virtual environment at env/bin/activate"
        source env/bin/activate
    else
        echo "WARNING: No virtual environment found. Installing dependencies globally..."
    fi
fi

echo ""
echo "Checking Python environment..."
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "ERROR: Python not found in PATH"
    echo "Please install Python 3.8+ and ensure it's in your PATH"
    exit 1
fi

# Use python3 if python command doesn't exist
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

echo "Using Python: $($PYTHON_CMD --version)"

echo ""
echo "Installing/updating dependencies..."
$PYTHON_CMD -m pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "WARNING: Some dependencies may have failed to install"
    echo "Trying to continue anyway..."
fi

echo ""
echo "Running pre-launch validation tests..."
$PYTHON_CMD validate.py
if [ $? -ne 0 ]; then
    echo "WARNING: Validation tests failed. The application may not work correctly."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Launch cancelled by user."
        exit 1
    fi
fi

echo ""
echo "================================================"
echo "  Starting Mini Antenna Designer..."
echo "================================================="
echo "Press Ctrl+C to stop the application"
echo ""

$PYTHON_CMD main.py
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "Application exited with error code $exit_code"
    echo "Check antenna_designer.log for detailed error information"
fi

echo ""
echo "Press Enter to exit..."
read -r
