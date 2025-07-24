import os
import subprocess
import re
from bs4 import BeautifulSoup

def convert_docx_to_html(docx_path, html_path, media_dir):
    cmd = [
        "pandoc", "-s", docx_path, "-o", html_path,
        f"--extract-media={media_dir}"
    ]
    # Suppress [WARNING] messages from pandoc
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Print only non-warning stderr lines
    for line in result.stderr.splitlines():
        if '[WARNING]' not in line:
            print(line)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)

def extract_images_from_html(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    # Map: qnum -> {"tables": [...], "images": [...]}
    q_map = {}
    # For storing context text for 'common' visuals
    common_contexts = []  # List of dicts: {context_text, tables, images}

    # Helper to find context text (e.g., Directions) for a node
    def find_context_text(node):
        while node:
            node = node.find_previous_sibling()
            if node and node.name == 'p':
                em = node.find('em')
                if em and 'Directions' in em.get_text():
                    return re.sub(r'\s+', ' ', em.get_text().strip())
        return None

    # Extract tables with robust mapping
    for idx, table in enumerate(soup.find_all("table")):
        table_html = str(table)
        qnum = None
        context_text = None
        node = table
        while node:
            node = node.find_previous_sibling()
            if node and node.name == 'p':
                strong = node.find('strong')
                if strong:
                    m = re.match(r"(\d+).", strong.get_text().strip())
                    if m:
                        qnum = int(m.group(1))
                        break
                # Check for directions block
                em = node.find('em')
                if em and 'Directions' in em.get_text():
                    context_text = re.sub(r'\s+', ' ', em.get_text().strip())
                    break
        if qnum is not None:
            if qnum not in q_map:
                q_map[qnum] = {"tables": [], "images": []}
            q_map[qnum]["tables"].append(table_html)
        elif context_text:
            found = False
            for ctx in common_contexts:
                if ctx["context_text"] == context_text:
                    ctx["tables"].append(table_html)
                    found = True
                    break
            if not found:
                common_contexts.append({"context_text": context_text, "tables": [table_html], "images": []})
        else:
            found = False
            for ctx in common_contexts:
                if ctx["context_text"] is None:
                    ctx["tables"].append(table_html)
                    found = True
                    break
            if not found:
                common_contexts.append({"context_text": None, "tables": [table_html], "images": []})

    # Extract images with robust mapping, including <img> inside <p> tags
    def process_img(img):
        img_src = img.get("src", "").strip()
        if not img_src:
            return
        # Find the nearest preceding question number or context
        qnum = None
        context_text = None
        # Look for the closest previous <p> with <strong>n.</strong> (question number)
        prev = img
        while True:
            prev = prev.find_previous_sibling()
            if prev is None:
                # If we hit the start of the document, try to walk up the parent chain to find a previous sibling <p> (for images inside nested tags)
                parent = img.parent
                while parent and parent != soup:
                    prev2 = parent.find_previous_sibling()
                    while prev2:
                        if prev2.name == 'p':
                            strong = prev2.find('strong')
                            if strong:
                                m = re.match(r"(\d+).", strong.get_text().strip())
                                if m:
                                    qnum = int(m.group(1))
                                    break
                        prev2 = prev2.find_previous_sibling()
                    if qnum is not None:
                        break
                    parent = parent.parent
                break
            if prev.name == 'p':
                strong = prev.find('strong')
                if strong:
                    m = re.match(r"(\d+).", strong.get_text().strip())
                    if m:
                        qnum = int(m.group(1))
                        break
                em = prev.find('em')
                if em and 'Directions' in em.get_text():
                    context_text = re.sub(r'\s+', ' ', em.get_text().strip())
                    break
        # If not found, also check parent <p> for question number
        if qnum is None and img.parent and img.parent.name == 'p':
            strong = img.parent.find('strong')
            if strong:
                m = re.match(r"(\d+).", strong.get_text().strip())
                if m:
                    qnum = int(m.group(1))
        if qnum is not None:
            if qnum not in q_map:
                q_map[qnum] = {"tables": [], "images": []}
            if img_src not in q_map[qnum]["images"]:
                q_map[qnum]["images"].append(img_src)
        else:
            # Try to find context text (Directions) if not already found
            if not context_text:
                context_text = find_context_text(img)
            if context_text:
                found = False
                for ctx in common_contexts:
                    if ctx["context_text"] == context_text:
                        if img_src not in ctx["images"]:
                            ctx["images"].append(img_src)
                        found = True
                        break
                if not found:
                    common_contexts.append({"context_text": context_text, "tables": [], "images": [img_src]})
            else:
                found = False
                for ctx in common_contexts:
                    if ctx["context_text"] is None:
                        if img_src not in ctx["images"]:
                            ctx["images"].append(img_src)
                        found = True
                        break
                if not found:
                    common_contexts.append({"context_text": None, "tables": [], "images": [img_src]})

    # Find all <img> tags anywhere in the document (including inside <p> tags)
    for img in soup.find_all("img"):
        process_img(img)

    # Additionally, find <img> tags inside <p> tags (if not already found)
    for p in soup.find_all("p"):
        for img in p.find_all("img"):
            process_img(img)

    # Convert to list of dicts
    result = []
    for qnum in sorted(q_map.keys(), key=lambda x: (str(x) != 'common', int(x) if str(x).isdigit() else 0)):
        result.append({"question_number": int(qnum), "tables": q_map[qnum]["tables"], "images": q_map[qnum]["images"]})
    # Add common-context visuals, but skip if context_text is None and only images are present
    for ctx in common_contexts:
        # Only add if context_text is not None, or if there are tables (for legacy)
        if ctx["context_text"] is not None or ctx["tables"]:
            result.append({
                "question_number": "common",
                "context_text": ctx["context_text"],
                "tables": ctx["tables"],
                "images": ctx["images"]
            })
    # Save the result to visuals.json in the same directory as the HTML
    visuals_json_path = os.path.join(os.path.dirname(html_path), "visuals.json")
    try:
        with open(visuals_json_path, "w", encoding="utf-8") as f:
            import json
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[extract_images_from_html] Visuals JSON saved to {visuals_json_path}")
    except Exception as e:
        print(f"[extract_images_from_html] Failed to save visuals JSON: {e}")
    return result

def extract_images_via_html(docx_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, "content.html")
    media_dir = os.path.join(output_dir, "media")
    convert_docx_to_html(docx_path, html_path, media_dir)
    images = extract_images_from_html(html_path)
    return images

if __name__ == "__main__":
    import argparse
    import json
    import sys
    # Try to import DOCX path from wordToMD.py if available
    docx_path = None
    try:
        import importlib.util
        import_path = os.path.join(os.path.dirname(__file__), 'wordToMD.py')
        spec = importlib.util.spec_from_file_location('wordToMD', import_path)
        wordToMD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wordToMD)
        # Try to get test_docx from wordToMD.py
        if hasattr(wordToMD, 'test_docx'):
            docx_path = wordToMD.test_docx
    except Exception as e:
        docx_path = None

    parser = argparse.ArgumentParser(description="Extract images and tables from DOCX via HTML")
    parser.add_argument('--docx', type=str, default=docx_path, help='Path to input DOCX file (default: from wordToMD.py)')
    parser.add_argument('--outdir', type=str, default='output_test/html_extraction', help='Output directory for HTML and extracted media')
    args = parser.parse_args()
    docx_path = args.docx
    output_dir = args.outdir
    if not docx_path:
        print("Error: No DOCX file specified and none found in wordToMD.py. Please provide --docx.")
        sys.exit(1)
    images = extract_images_via_html(docx_path, output_dir)
    print(f"Extracted {len(images)} images/tables from HTML:")
    # Save extracted visuals to JSON for downstream use, only if not already present
    visuals_json_path = os.path.join(output_dir, "visuals.json")
    test_json_path = os.path.join(output_dir, "visuals_test_output.json")
    import os
    import json
    if not os.path.exists(visuals_json_path):
        with open(visuals_json_path, "w", encoding="utf-8") as f:
            json.dump(images, f, ensure_ascii=False, indent=2)
        print(f"Visuals saved to {visuals_json_path}")
    else:
        print(f"Visuals file already exists: {visuals_json_path}")
    if not os.path.exists(test_json_path):
        with open(test_json_path, "w", encoding="utf-8") as f:
            json.dump(images, f, ensure_ascii=False, indent=2)
        print(f"Test visuals saved to {test_json_path}")
    else:
        print(f"Test visuals file already exists: {test_json_path}")
    # Print the full JSON content to the console for visibility
    print("\n===== Visuals JSON Output =====\n")
    print(json.dumps(images, ensure_ascii=False, indent=2))
