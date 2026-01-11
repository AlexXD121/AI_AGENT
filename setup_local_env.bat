@echo off
REM Sovereign-Doc Local Development Environment Setup (Python 3.12)
REM This script creates a Python 3.12 virtual environment with all dependencies

echo ============================================================
echo   SOVEREIGN-DOC LOCAL ENVIRONMENT SETUP (Python 3.12)
echo ============================================================
echo.

REM Step 1: Check if Python 3.12 is installed
echo [1/6] Checking for Python 3.12...
py -3.12 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python 3.12 not found!
    echo.
    echo Please install Python 3.12 using one of these methods:
    echo.
    echo   Option 1 - Using winget:
    echo     winget install Python.Python.3.12
    echo.
    echo   Option 2 - Manual download:
    echo     https://www.python.org/downloads/release/python-3120/
    echo.
    echo After installation, re-run this script.
    pause
    exit /b 1
)
echo   Python 3.12 found!

REM Step 2: Create virtual environment
echo.
echo [2/6] Creating virtual environment (.venv312)...
if exist .venv312 (
    echo   Virtual environment already exists. Deleting old one...
    rmdir /s /q .venv312
)
py -3.12 -m venv .venv312
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)
echo   Virtual environment created!

REM Step 3: Activate virtual environment
echo.
echo [3/6] Activating virtual environment...
call .venv312\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo   Virtual environment activated!

REM Step 4: Upgrade pip
echo.
echo [4/6] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo   Pip upgraded!

REM Step 5: Install dependencies
echo.
echo [5/6] Installing dependencies (this may take 5-10 minutes)...
echo   Installing core requirements...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Some requirements may have failed. Continuing...
)

echo   Installing vision dependencies...
pip install fastembed ultralytics paddleocr paddlepaddle pyngrok --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Some vision dependencies may have failed. Continuing...
)

echo   All dependencies installed!

REM Step 6: Run verification
echo.
echo [6/6] Running system verification...
echo.
python verify_system_status.py
set VERIFY_EXIT=%errorlevel%

echo.
echo ============================================================
echo   SETUP COMPLETE!
echo ============================================================
echo.
echo Next steps:
echo   1. Activate the environment: .venv312\Scripts\activate.bat
echo   2. Run verification: python verify_system_status.py
echo   3. Start developing!
echo.
echo To deactivate: deactivate
echo.

if %VERIFY_EXIT% neq 0 (
    echo [WARNING] System verification found some issues.
    echo Please review the output above.
)

pause
