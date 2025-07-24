import io
import os
import json
from PIL import Image, ImageDraw, ImageFont
from textwrap import wrap
import tempfile
import subprocess
import re
from html import unescape
from bs4 import BeautifulSoup, NavigableString

# You may need to adjust this path to a TTF font file available on your system
DEFAULT_FONT = os.path.join(os.path.dirname(__file__), '../dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf')

# --- Moved get_wrap_width_px to module level ---
def get_wrap_width_px(current_image_width, is_common):
    """
    Calculates the pixel width for text wrapping based on the current image width and content type.
    """
    # Common data/passages often benefit from slightly wider text area
    return int(current_image_width * 0.88) if is_common else int(current_image_width * 0.80)

def render_text_to_image(text, width=1600, font_path=DEFAULT_FONT, font_size=32, align='center', margin=60, line_spacing=1.5, bg_color='white', fg_color='black'):
    """
    Utility function to render simple text to an image.
    This function is separate from make_question_image's complex layout logic.
    """
    font = ImageFont.truetype(font_path, font_size)
    lines = []
    for para in text.split('\n'): # Explicitly split by newlines
        lines.extend(wrap(para, width=110)) # Then wrap sub-lines based on character width
    
    line_height = int(font_size * line_spacing)
    img_height = margin * 2 + line_height * len(lines)
    img = Image.new('RGB', (width, img_height), color=bg_color)
    draw = ImageDraw.Draw(img)
    y = margin
    for line in lines:
        try:
            # Ensure 'line' here is always a single visual line.
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
        except AttributeError:
            w, _ = font.getsize(line)
        if align == 'center':
            x = (width - w) // 2
        elif align == 'right':
            x = width - w - margin
        else: # 'left'
            x = margin
        draw.text((x, y), line, font=font, fill=fg_color)
        y += line_height
    return img

def make_question_image(q, out_path, font_path=DEFAULT_FONT):
    # Global configuration
    image_width = 1200  # Fixed width for consistency
    image_margin = 40
    line_spacing = 1.3
    font_sizes = {
        'common': 18,
        'question': 20,
        'option': 20,
        'default': 20
    }

    def setup_fonts(size):
        """Setup font variants for different styles"""
        font_dir = os.path.dirname(font_path)
        base_font = ImageFont.truetype(font_path, size)
        return {
            'normal': base_font,
            'bold': ImageFont.truetype(os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), size) if os.path.exists(os.path.join(font_dir, 'DejaVuSans-Bold.ttf')) else base_font,
            'italic': ImageFont.truetype(os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), size) if os.path.exists(os.path.join(font_dir, 'DejaVuSans-Oblique.ttf')) else base_font,
            'bold_italic': ImageFont.truetype(os.path.join(font_dir, 'DejaVuSans-BoldOblique.ttf'), size) if os.path.exists(os.path.join(font_dir, 'DejaVuSans-BoldOblique.ttf')) else base_font
        }

    # Font configuration for different text parts
    font_config = {
        'question': setup_fonts(font_sizes['question']),
        'option': setup_fonts(font_sizes['option']),
        'common': setup_fonts(font_sizes['common'])
    }

    def process_text_styles(text):
        """Process text for styling and clean HTML tags"""
        if not isinstance(text, str):
            return text
            
        # Handle HTML entities and escaped characters first
        text = unescape(text)
        text = re.sub(r'\\([<>"])', r'\1', text)
        
        # Clean up any escaped HTML tags
        text = re.sub(r'&lt;(?:strong|b|em|i|u)&gt;', lambda m: f'<{m.group(1)}>', text, flags=re.IGNORECASE)
        text = re.sub(r'&lt;/(?:strong|b|em|i|u)&gt;', lambda m: f'</{m.group(1)}>', text, flags=re.IGNORECASE)
        
        # Convert markdown to HTML styles
        text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        text = re.sub(r'\[([^\]]+)\](?:\.underline\}|\{\.underline\})', r'<u>\1</u>', text)
        
        # Standardize tags (convert all variants to standard form)
        replacements = [
            (r'<b\b[^>]*>', '<strong>'),
            (r'</b>', '</strong>'),
            (r'<STRONG\b[^>]*>', '<strong>'),
            (r'</STRONG>', '</strong>'),
            (r'<i\b[^>]*>', '<em>'),
            (r'</i>', '</em>'),
            (r'<EM\b[^>]*>', '<em>'),
            (r'</EM>', '</em>')
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

    def parse_html_runs(html_text):
        """Parse HTML and split into styled runs (support <strong>, <b>, <em>, <i>, <u>)"""
        if not isinstance(html_text, str):
            return [(str(html_text), {'bold': False, 'italic': False, 'underline': False})]
        
        soup = BeautifulSoup(html_text, 'html.parser')
        runs = []
        
        def walk(node, style):
            if isinstance(node, NavigableString):
                text = str(node)
                if text:
                    runs.append((text, style.copy()))
                return
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
            if not t: continue
            if merged and merged[-1][1] == s:
                merged[-1] = (merged[-1][0] + t, s)
            else:
                merged.append((t, s))
        return merged

    def has_html_style_tags(text):
        """Check if text contains any style markup"""
        if not isinstance(text, str):
            return False
        return bool(re.search(r'<(?:strong|b|em|i|u)>', text))

    # Process and prepare the blocks of content
    blocks_raw_content = []
    
    if q.get('main_common_data'):
        blocks_raw_content.append((q['main_common_data'], 'justify', 'common'))
        blocks_raw_content.append(('', 'blank_line_insert', 'blank'))
    if q.get('sub_common_data'):
        blocks_raw_content.append((q['sub_common_data'], 'justify', 'common'))
        blocks_raw_content.append(('', 'blank_line_insert', 'blank'))
    
    question_text_raw = q.get('Question', '')
    question_text_raw = question_text_raw.replace(r'\.', '.').replace('\\n', ' ').replace('\n', ' ').strip()
    match_q_num = re.match(r'^\s*(?:<[^>]+>)*\s*(\d+\s*\.)(?:\s*(?:</[^>]+>)*\s*)(.*)', question_text_raw, re.DOTALL | re.IGNORECASE)
    
    if match_q_num:
        main_question_text_str = match_q_num.group(2).strip()
    else:
        main_question_text_str = question_text_raw

    blocks_raw_content.append((main_question_text_str, 'justify', 'question'))
    blocks_raw_content.append(('', 'blank_line_insert', 'blank'))

    if q.get('Options'):
        for opt in q['Options']:
            blocks_raw_content.append((opt, 'left', 'option'))

    table_imgs = []
    classic_table_style = '''
        table { border-collapse: collapse; width: 100%; font-size: 22px; }
        th, td { border: 1px solid #222; padding: 8px; text-align: center; background: #fff; }
        th { background: #f2f2f2; font-weight: bold; }
        tr:nth-child(even) td { background: #f9f9f9; }
    '''
    if q.get('Table'):
        for table_html in q['Table']:
            with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as tf:
                tf.write(f"<html><head><meta charset='utf-8'><style>{classic_table_style}</style></head><body>{table_html}</body></html>")
                html_path = tf.name
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_temp:
                img_path = img_temp.name
            try:
                subprocess.run(['wkhtmltoimage', '--width', str(image_width - 80), '--quality', '90', html_path, img_path], check=True, capture_output=True)
                table_imgs.append(Image.open(img_path))
            except Exception as e:
                print(f"Failed to render table: {e}")
            finally:
                os.unlink(html_path)

    image_imgs = []
    image_margin = 40
    if q.get('Image'):
        for img_entry in q['Image']:
            img_path = None
            if isinstance(img_entry, str):
                m = re.search(r'src=["\']([^"\']+)["\']', img_entry)
                img_path = m.group(1) if m else img_entry
            if img_path:
                # Simplified path finding for clarity
                if not os.path.exists(img_path):
                    img_path = os.path.join(os.path.dirname(out_path), '..', 'media', os.path.basename(img_path))

                if os.path.exists(img_path):
                    try:
                        img = Image.open(img_path)
                        max_img_w = image_width - (2 * image_margin)
                        if img.width > max_img_w:
                            ratio = max_img_w / img.width
                            img = img.resize((max_img_w, int(img.height * ratio)), Image.LANCZOS)
                        image_imgs.append(img)
                    except Exception as e:
                        print(f"Failed to load image {img_path}: {e}")
                else:
                    print(f"Image not found: {img_path}")
    
    main_text_margin = 40
    min_variable_font_size = 14
    max_variable_font_size = 22
    line_spacing_multiplier = 1.3
    max_total_image_height = 2000

    def get_layout_metrics(font_config, current_image_width_for_layout):
        font_dir = os.path.dirname(font_path)
        # Create font objects for all required sizes
        fonts_by_size = {}
        for size in set(font_config.values()):
            if size not in fonts_by_size:
                base_font = ImageFont.truetype(font_path, size)
                fonts_by_size[size] = {
                    'normal': base_font,
                    'bold': ImageFont.truetype(os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), size) if os.path.exists(os.path.join(font_dir, 'DejaVuSans-Bold.ttf')) else base_font,
                    'italic': ImageFont.truetype(os.path.join(font_dir, 'DejaVuSans-Oblique.ttf'), size) if os.path.exists(os.path.join(font_dir, 'DejaVuSans-Oblique.ttf')) else base_font,
                    'bold_italic': ImageFont.truetype(os.path.join(font_dir, 'DejaVuSans-BoldOblique.ttf'), size) if os.path.exists(os.path.join(font_dir, 'DejaVuSans-BoldOblique.ttf')) else base_font,
                }

            def get_text_segments(text):
                """Split HTML-like styled text into segments with style information including bold, italic, and underline."""
                segments = []
                current_pos = 0
                style_stack = []

                tag_pattern = re.compile(r'<(/?)(strong|b|em|i|u)>', re.IGNORECASE)

                while current_pos < len(text):
                    match = tag_pattern.search(text, current_pos)
                    if not match:
                        # No more tags, flush remaining
                        style = {'bold': False, 'italic': False, 'underline': False}
                        for tag in style_stack:
                            if tag in ('strong', 'b'):
                                style['bold'] = True
                            elif tag in ('em', 'i'):
                                style['italic'] = True
                            elif tag == 'u':
                                style['underline'] = True
                        segments.append((text[current_pos:], style))
                        break

                    start, end = match.span()
                    if start > current_pos:
                        # Add preceding text
                        style = {'bold': False, 'italic': False, 'underline': False}
                        for tag in style_stack:
                            if tag in ('strong', 'b'):
                                style['bold'] = True
                            elif tag in ('em', 'i'):
                                style['italic'] = True
                            elif tag == 'u':
                                style['underline'] = True
                        segments.append((text[current_pos:start], style))

                    is_closing, tag = match.groups()
                    tag = tag.lower()
                    if is_closing:
                        if tag in style_stack:
                            style_stack.remove(tag)
                    else:
                        style_stack.append(tag)

                    current_pos = end

                return segments


        def get_text_segment_width(text_seg, style_info, font_set):
            key = 'normal'
            if style_info.get('bold') and style_info.get('italic'): key = 'bold_italic'
            elif style_info.get('bold'): key = 'bold'
            elif style_info.get('italic'): key = 'italic'
            fnt = font_set.get(key, font_set['normal'])
            return fnt.getlength(text_seg) if hasattr(fnt, 'getlength') else fnt.getsize(text_seg)[0]

        layout_lines = []
        total_height = 0

        for text_content, block_align_type, block_category in blocks_raw_content:
            font_size = font_config.get(block_category, font_config['default'])
            current_fonts = fonts_by_size[font_size]
            line_height = int(font_size * line_spacing_multiplier)
            
            if block_align_type == 'blank_line_insert':
                layout_lines.append(('', None, 'center', 'blank_inserted', 0, int(line_height * 0.5)))
                continue

            wrap_px = get_wrap_width_px(current_image_width_for_layout, block_category == 'common')
            
            for paragraph in text_content.split('\n'):
                if not paragraph.strip(): continue
                text_segments = get_text_segments(paragraph)
                current_line_segments = []
                current_line_width = 0
                
                for text, style in text_segments:
                    words = text.split(' ')
                    for word in words:
                        word_to_measure = ('' if not current_line_segments else ' ') + word
                        word_width = get_text_segment_width(word_to_measure, style, current_fonts)
                        
                        if current_line_segments and current_line_width + word_width > wrap_px:
                            # Line is full, add it to layout
                            layout_lines.append(('', current_fonts, block_align_type, block_category, current_line_width, line_height, current_line_segments))
                            current_line_segments = [(word, style)]
                            current_line_width = get_text_segment_width(word, style, current_fonts)
                        else:
                            current_line_segments.append((word_to_measure, style))
                            current_line_width += word_width
                if current_line_segments:
                    layout_lines.append(('', current_fonts, block_align_type, block_category, current_line_width, line_height, current_line_segments))

        # Calculate total height by summing up line heights (access line_height which is the 6th element)
        total_height = sum(line[5] if len(line) >= 6 else 0 for line in layout_lines) + (2 * main_text_margin)
        return layout_lines, total_height, fonts_by_size

    lines_to_render_final = []
    final_fonts_by_size = {}
    
    variable_font_size = max_variable_font_size
    while variable_font_size >= min_variable_font_size:
        font_config = {
            'common': font_sizes['common'],
            'question': variable_font_size,
            'option': variable_font_size,
            'default': variable_font_size
        }
        
        lines_data, calculated_text_height, fonts_map = get_layout_metrics(font_config, image_width)
        
        total_content_height = calculated_text_height
        total_content_height += sum(t.height + image_margin for t in table_imgs)
        total_content_height += sum(i.height + image_margin for i in image_imgs)

        if total_content_height <= max_total_image_height or variable_font_size == min_variable_font_size:
            lines_to_render_final = lines_data
            final_fonts_by_size = fonts_map
            break
        
        variable_font_size -= 1

    # Calculate final height using line_height (6th element) from each line
    final_height = sum(line[5] if len(line) >= 6 else 0 for line in lines_to_render_final) + (2 * main_text_margin)
    # Add heights for tables and images
    final_height += sum(t.height + image_margin for t in table_imgs)
    final_height += sum(i.height + image_margin for i in image_imgs)
    
    final_image = Image.new('RGB', (image_width, int(final_height)), color='white')
    draw = ImageDraw.Draw(final_image)
    y = main_text_margin

    for line in lines_to_render_final:
        if len(line) < 6:  # Skip invalid lines
            continue
            
        content, fonts_set, align, category, width, line_height = line[:6]
        if category == 'blank_inserted':
            y += line_height
            continue
        
        x = main_text_margin
        if align == 'center':
            x = (image_width - width) // 2
        elif align == 'right':
            x = image_width - width - image_margin
        
        if len(line) == 7:  # New format with segments
            current_x = x
            segments = line[6]
            for segment_text, style in segments:
                font_key = 'normal'
                if style.get('bold') and style.get('italic'): font_key = 'bold_italic'
                elif style.get('bold'): font_key = 'bold'
                elif style.get('italic'): font_key = 'italic'
                
                segment_font = fonts_set[font_key]
                # Draw text
                draw.text((current_x, y), segment_text, font=segment_font, fill='black')
                
                # Draw underline if needed
                if style.get('underline'):
                    try:
                        bbox = draw.textbbox((current_x, y), segment_text, font=segment_font)
                        underline_y = bbox[3] + 2
                        draw.line((bbox[0], underline_y, bbox[2], underline_y), fill='black', width=2)
                    except AttributeError:
                        # Fallback for older Pillow versions
                        text_width = segment_font.getsize(segment_text)[0]
                        draw.line((current_x, y + segment_font.getsize(segment_text)[1] + 2,
                                current_x + text_width, y + segment_font.getsize(segment_text)[1] + 2),
                                fill='black', width=2)
                
                current_x += (segment_font.getlength(segment_text) if hasattr(segment_font, 'getlength') 
                            else segment_font.getsize(segment_text)[0])
        else:  # Old format without styling
            draw.text((x, y), content, font=fonts_set['normal'], fill='black')
        y += line_height

    for timg in table_imgs:
        final_image.paste(timg, ((image_width - timg.width) // 2, y))
        y += timg.height + image_margin
    
    for iimg in image_imgs:
        final_image.paste(iimg, ((image_width - iimg.width) // 2, y))
        y += iimg.height + image_margin
        
    final_image = final_image.crop((0, 0, image_width, y))
    
    # Simple save, compression logic can be re-added if necessary
    final_image.save(out_path, format='PNG', optimize=True, compress_level=9)
    
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate question images from DOCX or JSON')
    parser.add_argument('--docx', type=str, default=None, help='Path to input DOCX file (optional, will run full pipeline if provided)')
    parser.add_argument('--json', type=str, default=None, help='Path to cleaned JSON (optional, overrides DOCX if provided)')
    parser.add_argument('--outdir', type=str, default='../output_test/question_images', help='Output directory')
    parser.add_argument('--docxname', type=str, default=None, help='Original Word document name (without extension)')
    parser.add_argument('--font', type=str, default=DEFAULT_FONT, help='Font path')
    args = parser.parse_args()

    try:
        from md_cleaner import clean_markdown_content
        from md_to_json import parse_cleaned_markdown
        from wordToMD import convert_docx_to_markdown
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Please ensure 'md_cleaner.py', 'md_to_json.py', and 'wordToMD.py' are in your PYTHONPATH or the same directory.")
        return

    if args.docx:
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
        default_json = os.path.join(os.path.dirname(args.outdir), '../output_test/cleaned.json')
        if not os.path.exists(default_json):
            print(f"Error: No DOCX, JSON, or default '{default_json}' found. Please provide input.")
            return
        with open(default_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # Get base docx name and clean it up
    docx_base = args.docxname or os.path.splitext(os.path.basename(args.docx or args.json or 'dummy.json'))[0]
    # Remove cleaned and sections markers
    docx_base = docx_base.replace('cleaned','').replace('_sections','').strip('_')
    # Remove timestamp prefixes (both old 8+ digit format and new 13 digit format)
    docx_base = re.sub(r'^\d{8,}[-_]', '', docx_base)
    docx_base = re.sub(r'^\d{13}[-_]', '', docx_base)  # For 13-digit timestamps

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    conversions_dir = os.path.join(project_root, 'conversions')
    os.makedirs(conversions_dir, exist_ok=True)

    upload_dir = os.path.join(conversions_dir, docx_base)
    os.makedirs(upload_dir, exist_ok=True)

    import glob, shutil
    pattern = os.path.join(conversions_dir, '*-' + docx_base)
    matches = glob.glob(pattern)
    for old_dir in matches:
        if os.path.abspath(old_dir) != os.path.abspath(upload_dir):
            for item in os.listdir(old_dir):
                src = os.path.join(old_dir, item)
                dst = os.path.join(upload_dir, item)
                try:
                    if os.path.isdir(src):
                        if not os.path.exists(dst):
                            shutil.move(src, dst)
                    else:
                        shutil.move(src, dst)
                except shutil.Error as e:
                    print(f"Warning: Could not move {src} to {dst}: {e}. Possibly already exists or in use.")
            try:
                os.rmdir(old_dir)
            except OSError as e:
                print(f"Warning: Could not remove old directory {old_dir}: {e}. It might not be empty or in use.")

    content = data['Content']
    for section, section_data in content.items():
        section_label = section.strip()
        section_dir = os.path.join(upload_dir, section_label) if section_label else upload_dir
        os.makedirs(section_dir, exist_ok=True)
        
        questions = section_data['Data']['questions']
        for q_data in questions:
            q_num = q_data.get('Question Number', 'unknown')
            out_path = os.path.join(section_dir, f'question_{q_num}.png')
            make_question_image(q_data, out_path, font_path=args.font)

    print(f"Question images generated in: conversions/{docx_base}")

    zip_base = os.path.join(conversions_dir, docx_base)
    zip_path = shutil.make_archive(zip_base, 'zip', upload_dir)

    zip_dir, zip_file = os.path.split(zip_path)
    clean_zip_file = re.sub(r'^\d{8,}-', '', zip_file)
    clean_zip_path = os.path.join(zip_dir, clean_zip_file)
    if clean_zip_file != zip_file:
        os.rename(zip_path, clean_zip_path)
        zip_path = clean_zip_path
    print("===ZIP===")
    print(zip_path)

if __name__ == '__main__':
    main()
