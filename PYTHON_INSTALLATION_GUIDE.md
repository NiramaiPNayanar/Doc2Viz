# Python Installation Guide for DocxToImage

## Problem: Python Not Found

If you're seeing errors like "Python was not found", it means Python is not installed or not properly configured on your system.

## Solutions

### Option 1: Install Python from Official Website (Recommended)

1. **Download Python**:
   - Go to https://python.org/downloads/ 
   - Download Python 3.8 or newer for Windows
   - **IMPORTANT**: During installation, check "Add Python to PATH"

2. **Verify Installation**:
   ```cmd
   python --version
   ```
   Should show something like: `Python 3.11.x`

### Option 2: Install Python from Microsoft Store

1. Open Microsoft Store
2. Search for "Python"
3. Install "Python 3.11" (or latest version)
4. This automatically adds Python to PATH

### Option 3: Use Windows Python Launcher

If you have Python installed but the command isn't working:
```cmd
py --version
```

## After Installing Python

1. **Check Python Installation**:
   ```cmd
   python check_python.py
   ```

2. **Install Required Python Packages**:
   ```cmd
   pip install -r requirements.txt
   ```

3. **Install System Dependencies**:
   - **Pandoc**: Download from https://pandoc.org/installing.html
   - **wkhtmltopdf**: Download from https://wkhtmltopdf.org/downloads.html

## Troubleshooting

### Python Command Not Found
- Make sure Python is added to your PATH
- Try using `py` instead of `python`
- Restart your command prompt/VS Code after installation

### Permission Errors
- Run command prompt as Administrator
- Or use: `python -m pip install package_name`

### Path Issues
- Check if Python is in your PATH: `echo %PATH%`
- Add Python manually to PATH if needed

## Quick Test

After installation, test the system:
```cmd
python check_python.py
```

This will verify that all dependencies are properly installed.

## Still Having Issues?

1. **Restart VS Code** after installing Python
2. **Check Windows App Execution Aliases**:
   - Settings > Apps > Advanced app settings > App execution aliases
   - Disable Python aliases if causing conflicts
3. **Use absolute Python path** in the upload route if needed
