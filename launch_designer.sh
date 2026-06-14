#!/bin/bash
# Mini Antenna Designer Launcher (Unix/Linux/Mac) - robust, dependency-aware
cd "$(dirname "$0")" || exit 1

echo "================================================"
echo "  Mini Antenna Designer - Launcher"
echo "================================================"
echo ""

# --- 1. Find a Python interpreter ------------------------------------------
if command -v python3 &> /dev/null; then
    PY="python3"
elif command -v python &> /dev/null; then
    PY="python"
else
    echo "ERROR: Python not found."
    echo "Install Python 3.8+ from https://www.python.org/downloads/ (or your package manager)."
    exit 1
fi
echo "Using interpreter: $PY ($($PY --version 2>&1))"

# --- 2. Activate a virtual environment if one exists -----------------------
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Virtual environment active: $VIRTUAL_ENV"
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate && PY="python"
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate && PY="python"
fi

# --- 3. Ensure pip ---------------------------------------------------------
$PY -m pip --version &> /dev/null || $PY -m ensurepip --upgrade &> /dev/null

# --- 4. Install dependencies only if something is missing ------------------
echo ""
echo "Checking dependencies..."
if ! $PY -c "import numpy, scipy, matplotlib, shapely, ezdxf, loguru" &> /dev/null; then
    echo "Installing missing dependencies from requirements.txt ..."
    $PY -m pip install --upgrade pip &> /dev/null
    if ! $PY -m pip install -r requirements.txt; then
        echo ""
        echo "ERROR: Dependency installation failed."
        echo "Run manually to see the error:  $PY -m pip install -r requirements.txt"
        exit 1
    fi
else
    echo "All core dependencies present."
fi

# --- 5. Verify the GUI toolkit --------------------------------------------
if ! $PY -c "import tkinter" &> /dev/null; then
    echo ""
    echo "ERROR: tkinter (GUI toolkit) is not available."
    echo "  Debian/Ubuntu: sudo apt install python3-tk"
    echo "  Fedora:        sudo dnf install python3-tkinter"
    echo "  macOS:         install Python from python.org (includes Tk)"
    exit 1
fi

# --- 6. Launch -------------------------------------------------------------
echo ""
echo "================================================"
echo "  Starting Mini Antenna Designer..."
echo "================================================"
echo ""
$PY main.py
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "Application exited with error code $exit_code"
    echo "Check antenna_designer.log for details."
fi
