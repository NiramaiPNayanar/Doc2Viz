# Doc2Viz

Convert Word documents (DOCX) into visually rendered images through a clean transformation pipeline.

## 🚀 Overview

**Doc2Viz** implements a seamless flow:


It automates formatting, cleans Markdown, converts to JSON, and then renders to image using Python + PIL.

---

## 📦 Features

- Strips extra Markdown formatting via `md_cleaner`
- Converts cleaned Markdown/HTML to JSON
- Renders text, tables, and images into PNG via Python `Pillow`
- Robust handling of LaTeX, underlines, and placeholders
- Organizes output into a `conversions/<original_filename>/` directory

---

## 🛠️ Installation

### Requirements
- Python 3.8+
- `Pillow`, `pylatexenc`, `beautifulsoup4`

### Install dependencies

```bash
pip install Pillow pylatexenc beautifulsoup4

