#!/bin/bash

echo "Installing Python dependencies for DOCX to Image processor..."

# Install Python packages
pip install Pillow>=8.0.0
pip install beautifulsoup4>=4.9.0
pip install imgkit>=1.2.0
pip install mammoth>=1.4.0
pip install markdown>=3.3.0
pip install pylatexenc>=2.10

echo "Python dependencies installed successfully!"
echo ""
echo "IMPORTANT: You also need to install system dependencies:"
echo "1. Pandoc: https://pandoc.org/installing.html"
echo "2. wkhtmltopdf: https://wkhtmltopdf.org/downloads.html"
echo ""
echo "For Windows users:"
echo "- Download and run the Pandoc installer"
echo "- Download and run the wkhtmltopdf installer"
echo ""
echo "For Ubuntu/Debian users:"
echo "- sudo apt-get install pandoc wkhtmltopdf"
echo ""
echo "For macOS users:"
echo "- brew install pandoc wkhtmltopdf"
