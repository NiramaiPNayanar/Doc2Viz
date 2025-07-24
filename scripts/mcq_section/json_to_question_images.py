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
    if q.get('main_common_data'):
        blocks.append((q['main_common_data'], 'left'))
    if q.get('sub_common_data'):
        blocks.append((q['sub_common_data'], 'left'))
    if q.get('Question'):
        blocks.append((q['Question'], 'center'))  # Center the question
    if q.get('Options'):
        for opt in q['Options']:
            blocks.append((opt, 'left'))  # Left align each option

    # If there are tables, render them using wkhtmltopdf and insert as images
    import tempfile
    import subprocess
    from PIL import Image
    table_imgs = []
    # Render tables from q['Table'] (from cleaned JSON)
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
                # Classic HTML wrapper for table
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
            # Use wkhtmltoimage (from wkhtmltopdf suite) to render HTML table to PNG
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

    # Also render tables from visuals.json if available and mapped to this question
    # visuals.json should be in the output_test dir (2 levels up from out_path)
    try:
        out_test_dir = os.path.abspath(os.path.join(os.path.dirname(out_path), '..', '..'))
        visuals_path = os.path.join(out_test_dir, 'html_extraction', 'visuals.json')
        if os.path.exists(visuals_path):
            import json as _json
            with open(visuals_path, 'r', encoding='utf-8') as vf:
                visuals = _json.load(vf)
            # visuals.json is a list of dicts, each with 'question_number' and 'tables'
            qno = q.get('Question Number') or q.get('question_number')
            if qno is not None:
                for entry in visuals:
                    entry_qno = entry.get('Question Number') or entry.get('question_number')
                    if str(entry_qno) == str(qno):
                        for table_html in entry.get('tables', []):
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
                                print(f"Failed to render table from visuals.json with wkhtmltoimage: {e}")
                            finally:
                                os.unlink(html_path)
                                # Optionally, keep img_path for debugging
                                # os.unlink(img_path)
    except Exception as e:
        print(f"Error loading or rendering tables from visuals.json: {e}")

    # If there are images (from the JSON 'Image' field), load them to paste after options/at last
    image_imgs = []
    # Render each block with its alignment, ensuring text fits in the image
    width = 1600
    margin = 60
    min_img_width = 400
    max_img_width = int(0.9 * width) // 2  # Allow up to 2 per row, 90% of width
    min_img_height = 200
    max_img_height = 700
    if q.get('Image'):
        for img_path in q['Image']:
            try:
                img_full_path = img_path
                # If the path is relative, resolve relative to the output_test dir (2 levels up from out_path)
                if not os.path.isabs(img_full_path):
                    out_test_dir = os.path.abspath(os.path.join(os.path.dirname(out_path), '..', '..'))
                    img_full_path = os.path.normpath(os.path.join(out_test_dir, img_full_path))
                if os.path.exists(img_full_path):
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
                    print(f"Image not found: {img_full_path}")
            except Exception as e:
                print(f"Failed to load image {img_path}: {e}")

    # Render each block with its alignment, ensuring text fits in the image
    width = 1600
    margin = 60
    min_font_size = 18
    max_font_size = 32
    wrap_width = 80
    from textwrap import wrap

    def get_lines_and_height(font_size):
        font = ImageFont.truetype(font_path, font_size)
        lines = []
        aligns = []
        block_types = []  # Track block type for justification
        for text, align in blocks:
            is_question = (align == 'center' and text == q.get('Question'))
            for para in text.split('\n'):
                wrapped = wrap(para, width=wrap_width)
                if not wrapped:
                    lines.append('')
                    aligns.append(align)
                    block_types.append('question' if is_question else 'other')
                else:
                    for wline in wrapped:
                        lines.append(wline)
                        aligns.append(align)
                        block_types.append('question' if is_question else 'other')
            # Add a blank line after each block except options
            if align != 'left' or text == q.get('Question'):
                lines.append('')
                aligns.append('center')
                block_types.append('other')
        line_height = int(font_size * 1.5)
        text_height = margin * 2 + line_height * len(lines)
        return lines, aligns, block_types, line_height, text_height, font

    # Try to fit text with decreasing font size
    font_size = max_font_size
    max_img_height = 900  # Further decrease the height of the question image
    while font_size >= min_font_size:
        lines, aligns, block_types, line_height, text_height, font = get_lines_and_height(font_size)
        img_height = text_height
        for timg in table_imgs:
            img_height += timg.height + 30
        for iimg in image_imgs:
            img_height += iimg.height + 30
        # No max_img_height check: always use content height
        break

    # Draw on a tall temp image, then crop to content
    temp_img = Image.new('RGB', (width, img_height), color='white')
    draw = ImageDraw.Draw(temp_img)
    y = margin
    n_lines = len(lines)
    for idx, (line, align, block_type) in enumerate(zip(lines, aligns, block_types)):
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except AttributeError:
            w, h = font.getsize(line)
        # Justify question lines except last line of the question block
        if block_type == 'question' and align == 'center':
            # Find if this is the last line of the question block
            is_last = False
            for j in range(idx+1, n_lines):
                if block_types[j] == 'question':
                    is_last = False
                    break
                if block_types[j] != 'question':
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
        elif align == 'center':
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
    parser.add_argument('--outdir', type=str, default=None, help='Output directory (default: conversions/<upload_folder> at project root)')
    parser.add_argument('--docxname', type=str, default=None, help='Original Word document name (without extension)')
    parser.add_argument('--filename', type=str, default=None, help='Alias for --docxname (for compatibility)')
    parser.add_argument('--font', type=str, default=None, help='Font path')
    args = parser.parse_args()

    # Support --filename as an alias for --docxname
    if args.filename and not args.docxname:
        args.docxname = args.filename

    # Load data
    if args.docx:
        from wordToMD import convert_docx_to_markdown
        from md_cleaner import clean_markdown_content
        from md_to_json import parse_cleaned_markdown
        output_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output_test'))
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
        default_json = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output_test', 'cleaned.json'))
        with open(default_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # Font path
    font_path = args.font or os.path.join(os.path.dirname(__file__), '../dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf')


    # Determine upload folder name: --docxname/--filename, else fallback to JSON filename
    upload_folder = None
    if args.docxname:
        upload_folder = args.docxname.strip()
    elif args.docx:
        upload_folder = os.path.splitext(os.path.basename(args.docx))[0].strip()
    elif args.json:
        # Try to infer from JSON filename
        base = os.path.splitext(os.path.basename(args.json))[0]
        upload_folder = base.replace('cleaned','').replace('_sections','').strip('_').strip()
    # Remove trailing or embedded '.docx' from upload_folder
    if upload_folder and upload_folder.lower().endswith('.docx'):
        upload_folder = upload_folder[:-5]
    upload_folder = upload_folder.replace('.docx', '').replace('docx', '').strip('_').strip()
    
    # Remove timestamps from upload folder name
    if upload_folder:
        import re
        # Remove timestamp prefix patterns (e.g., 1752257752115-QWHO2502504 -> QWHO2502504)
        upload_folder = re.sub(r'^\d{8,}-', '', upload_folder)  # Remove leading digits followed by dash
        
        # Remove various timestamp suffix patterns:
        # Pattern 1: _YYYYMMDD_HHMMSS (e.g., _20241201_143022)
        upload_folder = re.sub(r'_\d{8}_\d{6}$', '', upload_folder)
        # Pattern 2: _YYYY-MM-DD_HH-MM-SS (e.g., _2024-12-01_14-30-22)
        upload_folder = re.sub(r'_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$', '', upload_folder)
        # Pattern 3: _YYYYMMDDHHMMSS (e.g., _20241201143022)
        upload_folder = re.sub(r'_\d{14}$', '', upload_folder)
        # Pattern 4: Unix timestamp (10 digits, e.g., _1701434202)
        upload_folder = re.sub(r'_\d{10}$', '', upload_folder)
        # Pattern 5: Unix timestamp with milliseconds (13 digits, e.g., _1701434202123)
        upload_folder = re.sub(r'_\d{13}$', '', upload_folder)
        # Pattern 6: Any trailing sequence of digits longer than 8 characters (likely timestamp)
        upload_folder = re.sub(r'_\d{8,}$', '', upload_folder)
        upload_folder = upload_folder.strip('_').strip()
    
    # Do not fallback to data.get('filename') or any default
    if not upload_folder:
        print("Error: No valid filename provided for upload folder. Use --docxname or --filename, or provide a valid DOCX/JSON filename.")
        return

    # Output directory: <project_root>/conversions/<upload_folder>/<section>/
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    conversions_dir = os.path.join(project_root, 'conversions')
    outdir = args.outdir or os.path.join(conversions_dir, upload_folder)
    os.makedirs(outdir, exist_ok=True)
    print(f"Images will be saved in: {os.path.abspath(outdir)}")

    # Get content
    content = data['Content']
    # Iterate over all sections
    for section, section_data in content.items():
        section_label = section.strip()
        # If section_label is empty, dump images directly in outdir
        if not section_label:
            section_dir = outdir
        else:
            section_dir = os.path.join(outdir, section_label)
            os.makedirs(section_dir, exist_ok=True)
        questions = section_data['Data']['questions']
        for q in questions:
            qno = q.get('Question Number', 'unknown')
            out_path = os.path.join(section_dir, f'question_{qno}.png')
            make_question_image(q, out_path, font_path=font_path)
            # print(f"Saved: {out_path}")

    # Zip the upload_folder and print the path
    import shutil
    zip_base = os.path.join(conversions_dir, upload_folder)
    zip_path = shutil.make_archive(zip_base, 'zip', outdir)
    
    print("===ZIP===")
    print(os.path.abspath(zip_path))
    # Ensure no other print statements after the zip path

if __name__ == '__main__':
    main()
