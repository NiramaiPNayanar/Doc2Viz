@echo off
echo Installing Python dependencies for DOCX to Image processor...

pip install Pillow
pip install beautifulsoup4
pip install imgkit
pip install mammoth
pip install markdown
pip install pylatexenc

echo.
echo Python dependencies installed successfully!
echo.
echo IMPORTANT: You also need to install system dependencies:
echo 1. Pandoc: https://pandoc.org/installing.html
echo 2. wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
echo.
echo For Windows users:
echo - Download and run the Pandoc installer
echo - Download and run the wkhtmltopdf installer
echo.
pause
