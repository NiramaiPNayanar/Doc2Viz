#!/usr/bin/env python3
"""
Python Installation Check Script
This script verifies that Python is properly installed and accessible.
"""

import sys
import subprocess
import importlib.util

def check_python_installation():
    """Check if Python is properly installed and accessible."""
    print("=" * 50)
    print("Python Installation Check")
    print("=" * 50)
    
    # Check Python version
    print(f"✓ Python executable: {sys.executable}")
    print(f"✓ Python version: {sys.version}")
    print(f"✓ Platform: {sys.platform}")
    
    # Check required packages
    required_packages = [
        'PIL',  # Pillow
        'bs4',  # BeautifulSoup4
        'imgkit',
        'mammoth',
        'markdown',
        'pylatexenc'
    ]
    
    print("\nChecking required packages:")
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PIL':
                import PIL
                print(f"✓ Pillow (PIL): {PIL.__version__}")
            elif package == 'bs4':
                import bs4
                print(f"✓ BeautifulSoup4: {bs4.__version__}")
            elif package == 'imgkit':
                import imgkit
                print(f"✓ imgkit: Available")
            elif package == 'mammoth':
                import mammoth
                print(f"✓ mammoth: Available")
            elif package == 'markdown':
                import markdown
                print(f"✓ markdown: {markdown.__version__}")
            elif package == 'pylatexenc':
                import pylatexenc
                print(f"✓ pylatexenc: {pylatexenc.__version__}")
        except ImportError:
            print(f"✗ {package}: NOT INSTALLED")
            missing_packages.append(package)
    
    # Check external dependencies
    print("\nChecking external dependencies:")
    
    # Check pandoc
    try:
        result = subprocess.run(['pandoc', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ Pandoc: {version_line}")
        else:
            print("✗ Pandoc: Error running pandoc")
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        print("✗ Pandoc: NOT INSTALLED")
        print("  Install from: https://pandoc.org/installing.html")
    
    # Check wkhtmltopdf
    try:
        result = subprocess.run(['wkhtmltopdf', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ wkhtmltopdf: {version_line}")
        else:
            print("✗ wkhtmltopdf: Error running wkhtmltopdf")
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        print("✗ wkhtmltopdf: NOT INSTALLED")
        print("  Install from: https://wkhtmltopdf.org/downloads.html")
    
    print("\n" + "=" * 50)
    
    if missing_packages:
        print("Missing Python packages:")
        for pkg in missing_packages:
            print(f"  pip install {pkg}")
        print("\nOr install all at once:")
        print("  pip install -r requirements.txt")
        return False
    else:
        print("✓ All Python packages are installed!")
        return True

if __name__ == "__main__":
    success = check_python_installation()
    if success:
        print("\n🎉 Python environment is ready for DOCX processing!")
        sys.exit(0)
    else:
        print("\n❌ Please install missing dependencies before proceeding.")
        sys.exit(1)
