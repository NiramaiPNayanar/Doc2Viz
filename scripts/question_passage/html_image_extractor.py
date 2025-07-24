import os
import subprocess
import re
from bs4 import BeautifulSoup

def convert_docx_to_html(docx_path, html_path, media_dir):
    cmd = [
        "pandoc", "-s", docx_path, "-o", html_path,
        f"--extract-media={media_dir}"
    ]
    subprocess.run(cmd, check=True)

def extract_images_from_html(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    # Map: qnum -> {"tables": [...], "images": [...]}
    q_map = {}
    # For storing context text for 'common' visuals
    common_contexts = []  # List of dicts: {context_text, tables, images}

    # Helper to map a visual (table or image) to qnum/context
    def map_visual_to_qnum_or_context(qnum, context_text, visual_type, visual_html, q_map, common_contexts):
        if qnum is not None:
            if qnum not in q_map:
                q_map[qnum] = {"tables": [], "images": []}
            q_map[qnum][visual_type].append(visual_html)
        elif context_text:
            found = False
            for ctx in common_contexts:
                if ctx["context_text"] == context_text:
                    ctx[visual_type].append(visual_html)
                    found = True
                    break
            if not found:
                ctx = {"context_text": context_text, "tables": [], "images": []}
                ctx[visual_type].append(visual_html)
                common_contexts.append(ctx)
        else:
            found = False
            for ctx in common_contexts:
                if ctx["context_text"] is None:
                    ctx[visual_type].append(visual_html)
                    found = True
                    break
            if not found:
                ctx = {"context_text": None, "tables": [], "images": []}
                ctx[visual_type].append(visual_html)
                common_contexts.append(ctx)

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
                if em and 'Directions for question' in em.get_text():
                    context_text = re.sub(r'\s+', ' ', em.get_text().strip()).lower()
                    break
        map_visual_to_qnum_or_context(qnum, context_text, "tables", table_html, q_map, common_contexts)

    # Extract images with robust context mapping (like tables)
    for idx, img in enumerate(soup.find_all("img")):
        img_html = str(img)
        qnum = None
        context_text = None
        # Walk up the DOM tree to find the nearest directions <p> (not just siblings)
        found_context = False
        node = img
        while node:
            node = node.previous_element
            if node and getattr(node, 'name', None) == 'p':
                em = node.find('em') if hasattr(node, 'find') else None
                if em and ('Directions for question' in em.get_text() or 'Directions for questions' in em.get_text()):
                    # Collect all adjacent <p> blocks above as context
                    context_blocks = [em.get_text().strip()]
                    p2 = node.previous_sibling
                    while p2 and getattr(p2, 'name', None) == 'p':
                        context_blocks.insert(0, p2.get_text().strip())
                        p2 = p2.previous_sibling
                    context_blocks = [b for b in context_blocks if b.strip()]
                    context_text = ' '.join(context_blocks).strip()
                    if context_text:
                        context_text = context_text.lower()
                    found_context = True
                    print(f"[Image Extraction] Found context for image: {context_text}")
                    break
        # If not found, look for question number as before (previous siblings only)
        if not found_context:
            node = img
            while node:
                node = node.find_previous_sibling()
                if node and node.name == 'p':
                    strong = node.find('strong')
                    if strong:
                        m = re.match(r"(\d+).", strong.get_text().strip())
                        if m:
                            qnum = int(m.group(1))
                            print(f"[Image Extraction] Found qnum for image: {qnum}")
                            break
        print(f"[Image Extraction] Adding image: qnum={qnum}, context_text={context_text}, img_html={img_html[:100]}...")
        map_visual_to_qnum_or_context(qnum, context_text, "images", img_html, q_map, common_contexts)

    # Convert to list of dicts
    result = []
    for qnum in sorted(q_map.keys(), key=lambda x: (str(x) != 'common', int(x) if str(x).isdigit() else 0)):
        # If any image/table in this qnum has a context, include it (not typical for qnum, but for completeness)
        entry = {
            "question_number": int(qnum),
            "tables": q_map[qnum]["tables"],
            "images": q_map[qnum]["images"]
        }
        result.append(entry)
    # Add common-context visuals (with context_text for both tables and images)
    for ctx in common_contexts:
        entry = {
            "question_number": "common",
            "context_text": ctx["context_text"],
            "tables": ctx["tables"],
            "images": ctx["images"]
        }
        result.append(entry)
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

    # Print only the image part for testing
    print("\n===== IMAGES ONLY (for testing) =====\n")
    for entry in images:
        if entry.get('images'):
            print(f"Images for entry (question_number={entry.get('question_number')}, context_text={entry.get('context_text')}):")
            for img in entry['images']:
                print(img)
