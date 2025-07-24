import os
import subprocess
import re
import json
from bs4 import BeautifulSoup

def convert_docx_to_html(docx_path, html_path, media_dir):
    cmd = [
        "pandoc", "-s", docx_path, "-o", html_path,
        f"--extract-media={media_dir}"
    ]
    # Suppress TeX math conversion warnings from pandoc
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        filtered = []
        for line in result.stderr.splitlines():
            if line.startswith('[WARNING] Could not convert TeX math') and 'rendering as TeX' in line:
                continue
            filtered.append(line)
        # If any other stderr remains, raise error
        if filtered:
            raise RuntimeError('\n'.join(filtered))
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)

def extract_visuals_for_solutions(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    # List of solution visuals
    visuals = []
    # Map tables/images to nearest preceding question number (solution_number)
    def find_prev_qnum(node):
        while node:
            node = node.find_previous_sibling()
            if node and node.name == 'p':
                strong = node.find('strong')
                if strong:
                    m = re.match(r"(\d+).", strong.get_text().strip())
                    if m:
                        return int(m.group(1))
        return None
    # Tables
    for table in soup.find_all("table"):
        table_html = str(table)
        qnum = find_prev_qnum(table)
        visuals.append({
            "solution_number": qnum,
            "Table": [table_html],
            "Image": []
        })
    # Images
    for img in soup.find_all("img"):
        img_html = str(img)
        qnum = find_prev_qnum(img)
        visuals.append({
            "solution_number": qnum,
            "Table": [],
            "Image": [img_html]
        })
    return visuals

def extract_images_via_html(docx_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, "content.html")
    media_dir = os.path.join(output_dir, "media")
    convert_docx_to_html(docx_path, html_path, media_dir)
    visuals = extract_visuals_for_solutions(html_path)
    # Save visuals to JSON
    visuals_json_path = os.path.join(output_dir, "visuals.json")
    with open(visuals_json_path, "w", encoding="utf-8") as f:
        json.dump(visuals, f, ensure_ascii=False, indent=2)
    return visuals

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract images and tables from DOCX via HTML for Solutions format")
    parser.add_argument('--docx', type=str, required=True, help='Path to input DOCX file')
    parser.add_argument('--outdir', type=str, default='output_test/html_extraction', help='Output directory for HTML and extracted media')
    args = parser.parse_args()
    visuals = extract_images_via_html(args.docx, args.outdir)
    print(json.dumps(visuals, indent=2))
