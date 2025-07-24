import os
import json
from PIL import Image, ImageDraw, ImageFont

# You may need to adjust this path to a TTF font file available on your system
DEFAULT_FONT = os.path.join(os.path.dirname(__file__), '../dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf')

# Utility to wrap text for PIL
from textwrap import wrap

def render_text_to_image(text, width=1600, font_path=DEFAULT_FONT, font_size=32, align='center', margin=60, line_spacing=1.5, bg_color='white', fg_color='black'):
    font = ImageFont.truetype(font_path, font_size)
    # Increase wrap width for longer lines
    lines = []
    for para in text.split('\n'):
        lines.extend(wrap(para, width=110))
    # Calculate image height
    line_height = int(font_size * line_spacing)
    img_height = margin * 2 + line_height * len(lines)
    img = Image.new('RGB', (width, img_height), color=bg_color)
    draw = ImageDraw.Draw(img)
    y = margin
    for line in lines:
        # Use textbbox for accurate measurement (Pillow >=8.0.0), fallback to textlength/textsize
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback for older Pillow
            w, h = font.getsize(line)
        if align == 'center':
            x = (width - w) // 2
        elif align == 'right':
            x = width - w - margin
        else:
            x = margin
        draw.text((x, y), line, font=font, fill=fg_color)
        y += line_height
    return img

def make_question_image(q, out_path, font_path=DEFAULT_FONT):
    # Compose the text block, justify only the question, left-align options
    blocks = []
    def has_html_style_tags(text):
        if not text:
            return False
        tags = ['<strong>', '<b>', '<em>', '<i>', '<u>']
        return any(tag in text for tag in tags)

    if q.get('main_common_data'):
        if has_html_style_tags(q['main_common_data']):
            blocks.append((q['main_common_data'], 'center_html'))
        else:
            blocks.append((q['main_common_data'], 'center_justify'))
        blocks.append(('', 'left'))  # Add one line break after main common data
    if q.get('sub_common_data'):
        if has_html_style_tags(q['sub_common_data']):
            blocks.append((q['sub_common_data'], 'center_html'))
        else:
            blocks.append((q['sub_common_data'], 'center_justify'))
        blocks.append(('', 'left'))  # Add one line break after sub common data
    # If the question contains <strong>/<b>/<em>/<i>/<u>, mark as HTML for styled rendering
    if q.get('Question'):
        question_text = q['Question']
        if has_html_style_tags(question_text):
            blocks.append((question_text, 'center_html'))  # Special marker for HTML styled
        else:
            blocks.append((question_text, 'center'))  # Center the question
    if q.get('Options'):
        for opt in q['Options']:
            blocks.append((opt, 'left'))  # Left align each option

    # Dynamically adjust width if common data is very long
    # For directions (main_common_data), use a wider width for better readability
    base_width = 1600
    width = base_width
    max_width = 2600  # Increased max width for directions
    min_width = 1200
    common_data = q.get('main_common_data', '')
    if common_data:
        # Count number of characters in the common data (excluding whitespace)
        common_len = len(common_data.replace('\n', '').replace(' ', ''))
        if common_len > 600:
            width = max_width
        elif common_len > 400:
            width = 2200
        elif common_len < 200:
            width = min_width

    # If there are tables, render them using wkhtmltopdf and insert as images (from cleaned JSON only)
    import tempfile
    import subprocess
    from PIL import Image
    table_imgs = []
    classic_table_style = '''
        table { border-collapse: collapse; width: 100%; font-size: 22px; }
        th, td { border: 1px solid #222; padding: 8px; text-align: center; background: #fff; }
        th { background: #f2f2f2; font-weight: bold; }
        tr:nth-child(even) td { background: #f9f9f9; }
    '''
    if q.get('Table'):
        for idx, table_html in enumerate(q['Table']):
            with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as tf:
                html_path = tf.name
                tf.write(f"""
                <html><head>
                <meta charset='utf-8'>
                <style>
                {classic_table_style}
                </style>
                </head><body>{table_html}</body></html>
                """)
            img_temp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            img_temp.close()
            img_path = img_temp.name
            try:
                subprocess.run([
                    'wkhtmltoimage', '--width', '1200', '--quality', '90', html_path, img_path
                ], check=True)
                table_img = Image.open(img_path)
                table_imgs.append(table_img)
            except Exception as e:
                print(f"Failed to render table with wkhtmltoimage: {e}")
            finally:
                os.unlink(html_path)
                # Optionally, keep img_path for debugging
                # os.unlink(img_path)

    # If there are images (from the JSON 'Image' field), load them to paste after options/at last
    image_imgs = []
    margin = 40  # Reduced margin for less vertical gap
    min_img_width = 400
    max_img_width = int(0.9 * width) // 2  # Allow up to 2 per row, 90% of width
    min_img_height = 200
    max_img_height = 700
    import re
    if q.get('Image'):
        for img_entry in q['Image']:
            img_path = None
            # If entry is an <img ... src=...> HTML, extract src
            if isinstance(img_entry, str):
                m = re.search(r'src=["\']([^"\']+)["\']', img_entry)
                if m:
                    img_path = m.group(1)
                    # Normalize slashes for Windows/Unix compatibility
                    img_path = img_path.replace('\\', '/').replace('//', '/')
                else:
                    img_path = img_entry.replace('\\', '/').replace('//', '/')
            if img_path:
                try:
                    # Fix: If the path exists as-is (relative to cwd or absolute), use it directly
                    candidate_paths = []
                    # 1. As-is (relative to cwd or absolute)
                    candidate_paths.append(os.path.normpath(img_path))
                    # 2. Relative to out_path's parent
                    candidate_paths.append(os.path.normpath(os.path.join(os.path.dirname(out_path), img_path)))
                    # 3. Walk up to find output_test and join from there
                    import re as _re
                    norm_img_path = img_path
                    norm_img_path = _re.sub(r'(output_test/)+', 'output_test/', norm_img_path)
                    # Do NOT remove repeated media/ segments; sometimes correct path has media/media/
                    cur_dir = os.path.abspath(os.path.dirname(out_path))
                    for _ in range(6):
                        candidate = os.path.join(cur_dir, 'output_test')
                        if os.path.isdir(candidate):
                            candidate_paths.append(os.path.normpath(os.path.join(candidate, norm_img_path)))
                            break
                        cur_dir = os.path.dirname(cur_dir)
                    # Try all candidate paths, use the first that exists
                    img_full_path = None
                    for cpath in candidate_paths:
                        if os.path.exists(cpath):
                            img_full_path = cpath
                            break
                    if img_full_path and os.path.exists(img_full_path):
                        img = Image.open(img_full_path)
                        w, h = img.size
                        # Zoom up if image is small, shrink if too large
                        zoom = 1.0
                        if w < min_img_width:
                            zoom = min_img_width / w
                        elif w > max_img_width:
                            zoom = max_img_width / w
                        if h < min_img_height:
                            zoom = max(zoom, min_img_height / h)
                        elif h > max_img_height:
                            zoom = min(zoom, max_img_height / h)
                        w = int(w * zoom)
                        h = int(h * zoom)
                        img = img.resize((w, h), Image.LANCZOS)
                        image_imgs.append(img)
                    else:
                        print(f"Image not found: {img_path} (tried: {candidate_paths})")
                except Exception as e:
                    print(f"Failed to load image {img_path}: {e}")

    # Render each block with its alignment, ensuring text fits in the image
    width = width  # use the dynamically set width above
    margin = 60
    min_font_size = 18
    max_font_size = 32
    from textwrap import wrap

    def get_wrap_width_px(is_common):
        # Set wrap width in pixels, not characters, for more accurate wrapping
        # Use 90% of image width for text area
        return int(width * 0.88) if is_common else int(width * 0.80)

    def get_lines_and_height(font_size):
        font = ImageFont.truetype(font_path, font_size)
        # Prepare font variants
        font_dir = os.path.dirname(font_path)
        font_files = {
            'normal': font_path,
            'bold': os.path.join(font_dir, 'DejaVuSans-Bold.ttf'),
            'italic': os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'),
            'bold_italic': os.path.join(font_dir, 'DejaVuSans-BoldOblique.ttf'),
        }
        fonts = {k: ImageFont.truetype(v, font_size) if os.path.exists(v) else font for k, v in font_files.items()}
        lines = []
        aligns = []
        block_types = []  # Track block type for justification
        html_styles = []  # For each line, a list of (text, style) tuples
        from bs4 import BeautifulSoup
        def parse_html_runs(html):
            # Returns a flat list of (text, style_dict) tuples, preserving order and nesting
            soup = BeautifulSoup(html, 'html.parser')
            runs = []
            def walk(node, style):
                # If it's a NavigableString, add it
                from bs4 import NavigableString
                if isinstance(node, NavigableString):
                    text = str(node)
                    if text:
                        runs.append((text, style.copy()))
                    return
                # If it's a tag, update style and recurse
                if hasattr(node, 'name'):
                    tag = node.name.lower()
                    if tag in ['strong', 'b']:
                        style = style.copy(); style['bold'] = True
                    if tag in ['em', 'i']:
                        style = style.copy(); style['italic'] = True
                    if tag == 'u':
                        style = style.copy(); style['underline'] = True
                for child in getattr(node, 'children', []):
                    walk(child, style)
            walk(soup, {'bold': False, 'italic': False, 'underline': False})
            # Merge adjacent runs with same style
            merged = []
            for t, s in runs:
                if not t:
                    continue
                if merged and merged[-1][1] == s:
                    merged[-1] = (merged[-1][0] + t, s)
                else:
                    merged.append((t, s))
            return merged
        for idx, (text, align) in enumerate(blocks):
            is_question = (align.startswith('center') and text == q.get('Question'))
            is_common = (
                (align == 'center_justify' and (text == q.get('main_common_data') or text == q.get('sub_common_data')))
                or (align == 'center_html' and (text == q.get('main_common_data') or text == q.get('sub_common_data')))
            )
            # Set wrap width in pixels
            wrap_width = get_wrap_width_px(is_common)
            if align == 'center_html':
                # Parse HTML and split into styled runs (support <strong>, <b>, <em>, <i>, <u>)
                html_runs = parse_html_runs(text)
                # Word-based wrapping: do not break words, wrap at word boundaries, and wrap by pixel width
                all_lines = []
                all_styles = []
                curr_line = []
                curr_width = 0
                for t, style in html_runs:
                    words = t.split(' ')
                    for widx, word in enumerate(words):
                        seg = ((' ' if (curr_line or widx > 0) else '') + word)
                        # Measure width of this segment
                        font_key = 'normal'
                        if style.get('bold') and style.get('italic'):
                            font_key = 'bold_italic'
                        elif style.get('bold'):
                            font_key = 'bold'
                        elif style.get('italic'):
                            font_key = 'italic'
                        fnt = fonts.get(font_key, font)
                        seg_width = fnt.getlength(seg) if hasattr(fnt, 'getlength') else fnt.getsize(seg)[0]
                        # If adding this word would exceed wrap_width, flush current line
                        if curr_line and (curr_width + seg_width > wrap_width):
                            line_text = ''.join([seg for seg, _ in curr_line]).strip()
                            all_lines.append(line_text)
                            all_styles.append(curr_line)
                            curr_line = []
                            curr_width = 0
                        curr_line.append((seg, style))
                        curr_width += seg_width
                if curr_line:
                    line_text = ''.join([seg for seg, _ in curr_line]).strip()
                    all_lines.append(line_text)
                    all_styles.append(curr_line)
                for wline, wline_runs in zip(all_lines, all_styles):
                    lines.append(wline)
                    aligns.append('center')
                    block_types.append('question' if not is_common else 'common')
                    html_styles.append(wline_runs if wline_runs else [(wline, {'bold': False, 'italic': False, 'underline': False})])
            else:
                for para in text.split('\n'):
                    # Use PIL-based word wrapping for non-HTML blocks as well
                    words = para.split(' ')
                    curr_line = ''
                    curr_width = 0
                    curr_words = []
                    for word in words:
                        seg = (word if not curr_words else ' ' + word)
                        seg_width = font.getlength(seg) if hasattr(font, 'getlength') else font.getsize(seg)[0]
                        if curr_words and (curr_width + seg_width > wrap_width):
                            lines.append(''.join(curr_words))
                            aligns.append(align)
                            block_types.append('question' if is_question else ('common' if is_common else 'other'))
                            html_styles.append(None)
                            curr_words = [word]
                            curr_width = font.getlength(word) if hasattr(font, 'getlength') else font.getsize(word)[0]
                        else:
                            curr_words.append(seg)
                            curr_width += seg_width
                    if curr_words:
                        lines.append(''.join(curr_words))
                        aligns.append(align)
                        block_types.append('question' if is_question else ('common' if is_common else 'other'))
                        html_styles.append(None)
            # Add a blank line after each block except options and except after common data
            is_last_common = is_common and (idx == len(blocks)-1 or not (blocks[idx+1][1] == 'center_justify'))
            if align != 'left' or text == q.get('Question'):
                if not is_common or not is_last_common:
                    lines.append('')
                    aligns.append('center')
                    block_types.append('other')
                    html_styles.append(None)
        line_height = int(font_size * 1.5)
        text_height = margin * 2 + line_height * len(lines)
        return lines, aligns, block_types, line_height, text_height, font, fonts, html_styles

    # Try to fit text with decreasing font size
    font_size = max_font_size
    max_img_height = 900  # Further decrease the height of the question image
    while font_size >= min_font_size:
        lines, aligns, block_types, line_height, text_height, font, fonts, html_styles = get_lines_and_height(font_size)
        img_height = text_height
        for timg in table_imgs:
            img_height += timg.height + 30
        for iimg in image_imgs:
            img_height += iimg.height + 30
        break

    # Draw on a tall temp image, then crop to content
    temp_img = Image.new('RGB', (width, img_height), color='white')
    draw = ImageDraw.Draw(temp_img)
    y = margin
    n_lines = len(lines)
    for idx, (line, align, block_type) in enumerate(zip(lines, aligns, block_types)):
        html_style = html_styles[idx] if 'html_styles' in locals() else None
        if html_style:
            # Render styled HTML line (bold/italic/underline for <strong>/<b>/<em>/<i>/<u>)
            x = (width - draw.textlength(line, font=font)) // 2
            for t, style in html_style:
                # Determine font style
                font_key = 'normal'
                if style.get('bold') and style.get('italic'):
                    font_key = 'bold_italic'
                elif style.get('bold'):
                    font_key = 'bold'
                elif style.get('italic'):
                    font_key = 'italic'
                fnt = fonts.get(font_key, font)
                # Draw underline if needed
                if style.get('underline'):
                    draw.text((x, y), t, font=fnt, fill='black')
                    # Draw underline manually
                    try:
                        bbox = draw.textbbox((x, y), t, font=fnt)
                        underline_y = bbox[3] + 2
                        draw.line((bbox[0], underline_y, bbox[2], underline_y), fill='black', width=2)
                    except Exception:
                        pass
                else:
                    draw.text((x, y), t, font=fnt, fill='black')
                x += draw.textlength(t, font=fnt)
            y += line_height
            continue
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except AttributeError:
            w, h = font.getsize(line)
        # Justify question and common data lines except last line of their block
        if (block_type == 'question' and align == 'center') or (block_type == 'common' and align == 'center_justify'):
            # Find if this is the last line of the block
            is_last = False
            for j in range(idx+1, n_lines):
                if block_types[j] == block_type:
                    is_last = False
                    break
                if block_types[j] != block_type:
                    is_last = True
                    break
            else:
                is_last = True
            if not is_last and len(line.strip().split()) > 1:
                # Justify this line
                words = line.strip().split()
                n_spaces = len(words) - 1
                total_text_width = sum(draw.textlength(word, font=font) for word in words)
                space_width = (width - 2*margin - total_text_width) / n_spaces if n_spaces > 0 else 0
                x = margin
                for i, word in enumerate(words):
                    draw.text((x, y), word, font=font, fill='black')
                    word_width = draw.textlength(word, font=font)
                    x += word_width
                    if i < n_spaces:
                        x += space_width
                y += line_height
                continue
            else:
                # Center last line or single-word lines
                x = (width - w) // 2
        elif align == 'center' or align == 'center_justify':
            x = (width - w) // 2
        elif align == 'right':
            x = width - w - margin
        else:
            x = margin
        draw.text((x, y), line, font=font, fill='black')
        y += line_height
    # Paste table images after text
    for timg in table_imgs:
        temp_img.paste(timg, ((width - timg.width) // 2, y))
        y += timg.height + 30
    # Paste images from the JSON after tables (or after options)
    # Dynamically arrange images: 2 per row if both fit, else 1 per row
    img_margin = 40
    i = 0
    n = len(image_imgs)
    while i < n:
        # Try to fit two images in a row if possible
        if i+1 < n:
            img1 = image_imgs[i]
            img2 = image_imgs[i+1]
            total_width = img1.width + img2.width + img_margin
            if total_width <= width - 2*margin:
                # Both images fit side by side
                x1 = (width - total_width) // 2
                x2 = x1 + img1.width + img_margin
                y_row = y
                temp_img.paste(img1, (x1, y_row))
                temp_img.paste(img2, (x2, y_row))
                y += max(img1.height, img2.height) + img_margin
                i += 2
                continue
        # Otherwise, just one image per row
        img1 = image_imgs[i]
        x1 = (width - img1.width) // 2
        temp_img.paste(img1, (x1, y))
        y += img1.height + img_margin
        i += 1
    # Crop to content (remove extra bottom space)
    cropped_img = temp_img.crop((0, 0, width, y))
    cropped_img.save(out_path.replace('.png', '.jpg'), format='JPEG', quality=70, optimize=True)


def main():
    import argparse
    import os
    parser = argparse.ArgumentParser(description='Generate question images from DOCX or JSON')
    parser.add_argument('--docx', type=str, default=None, help='Path to input DOCX file (optional, will run full pipeline if provided)')
    parser.add_argument('--json', type=str, default=None, help='Path to cleaned JSON (optional, overrides DOCX if provided)')
    parser.add_argument('--outdir', type=str, default='../output_test/question_images', help='Output directory')
    parser.add_argument('--docxname', type=str, default=None, help='Original Word document name (without extension)')
    parser.add_argument('--font', type=str, default=DEFAULT_FONT, help='Font path')
    args = parser.parse_args()

    # If DOCX is provided, run the full pipeline
    if args.docx:
        from wordToMD import convert_docx_to_markdown
        from md_cleaner import clean_markdown_content
        from md_to_json import parse_cleaned_markdown
        output_base_dir = os.path.join(os.path.dirname(args.outdir), 'output_test')
        md_content, md_path, media_dir, extracted_images = convert_docx_to_markdown(
            args.docx, output_base_dir,
            extract_media=True, mathml=True, save_md=True, extract_images=True
        )
        cleaned_md_path = os.path.join(output_base_dir, 'cleaned.md')
        cleaned_content = clean_markdown_content(
            md_content,
            save_json=False,
            cleaned_md_path=cleaned_md_path
        )
        with open(cleaned_md_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        data = parse_cleaned_markdown(cleaned_md_path, extracted_images)
    elif args.json:
        with open(args.json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        # Default: try to use cleaned.json in output_test
        default_json = os.path.join(os.path.dirname(args.outdir), '../output_test/cleaned.json')
        with open(default_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # Use --docxname if provided, else fallback to JSON or default
    # Ensure filename is just the base name, not a path
    if args.docxname:
        filename = os.path.splitext(os.path.basename(args.docxname))[0]
        # Remove .docx extension if present
        if args.docxname.lower().endswith('.docx'):
            filename = args.docxname[:-5]
        else:
            filename = os.path.splitext(os.path.basename(args.docxname))[0]
    elif args.docx:
        filename = os.path.splitext(os.path.basename(args.docx))[0]
    elif args.json:
        filename = os.path.splitext(os.path.basename(args.json))[0].replace('cleaned','').replace('_sections','').strip('_')
    else:
        filename = 'docxfile'

    # Always create output in conversions/<filename>/<section>
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    conversions_dir = os.path.join(project_root, 'conversions')
    os.makedirs(conversions_dir, exist_ok=True)
    upload_dir = os.path.join(conversions_dir, filename)
    try:
        os.makedirs(upload_dir, exist_ok=True)
        print(filename)
        # print(f"[DEBUG] Created upload_dir: {os.path.abspath(upload_dir)}")
    except Exception as e:
        print(f"[ERROR] Could not create upload_dir {upload_dir}: {e}")

    content = data['Content']
    for section, section_data in content.items():
        section_label = section.strip() or 'default'
        section_dir = os.path.join(upload_dir, section_label)
        os.makedirs(section_dir, exist_ok=True)
        questions = section_data['Data']['questions']
        for q in questions:
            qno = q.get('Question Number', 'unknown')
            out_path = os.path.join(section_dir, f'question_{qno}.png')
            make_question_image(q, out_path, font_path=args.font)
            # print(f"Saved: {out_path}")

    # Zip the filename folder and print the path
    import shutil
    zip_base = os.path.join(conversions_dir, filename)
    zip_path = shutil.make_archive(zip_base, 'zip', upload_dir)
    print("===ZIP===")
    print(zip_path)

if __name__ == '__main__':
    main()
