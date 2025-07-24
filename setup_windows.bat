@echo off
echo ================================================
echo DocxToImage Setup Script for Windows
echo ================================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Python is installed
    python --version
) else (
    echo ✗ Python is not installed or not in PATH
    echo.
    echo Please install Python first:
    echo 1. Go to https://python.org/downloads/
    echo 2. Download and install Python 3.8 or newer
    echo 3. Make sure to check "Add Python to PATH" during installation
    echo 4. Restart this script after installation
    echo.
    pause
    exit /b 1
)

echo.
echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install Pillow>=8.0.0
python -m pip install beautifulsoup4>=4.9.0
python -m pip install imgkit>=1.2.0
python -m pip install mammoth>=1.4.0
python -m pip install markdown>=3.3.0
python -m pip install pylatexenc>=2.10

echo.
echo Running installation check...
python check_python.py

echo.
echo ================================================
echo Setup complete! 
echo.
echo IMPORTANT: You still need to install:
echo 1. Pandoc: https://pandoc.org/installing.html
echo 2. wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
echo ================================================
pause
