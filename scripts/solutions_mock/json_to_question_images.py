import os
import argparse
import json
from runpy import run_path
from PIL import Image, ImageDraw, ImageFont

def render_text_to_image(text, width=1600, font_path=None, font_size=32, align='justify', margin=60, line_spacing=1.5, bg_color='white', fg_color='black'):
    from textwrap import wrap
    from PIL import Image, ImageDraw, ImageFont
    
    font = ImageFont.truetype(font_path, font_size)
    max_text_width = width - 2 * margin
    
    # Create temporary image for text measurement
    temp_img = Image.new('RGB', (width, 100), color=bg_color)
    draw = ImageDraw.Draw(temp_img)
    
    # Wrap text into lines
    wrapped_lines = []
    for paragraph in text.split('\n'):
        words = paragraph.split()
        if not words:
            wrapped_lines.append('')
            continue
            
        line = words[0]
        for word in words[1:]:
            test_line = line + ' ' + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_text_width:
                line = test_line
            else:
                wrapped_lines.append(line)
                line = word
        wrapped_lines.append(line)
    
    # Calculate image height
    line_height = int(font_size * line_spacing)
    img_height = margin * 2 + line_height * len(wrapped_lines)
    img = Image.new('RGB', (width, img_height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    y = margin
    max_height = img_height - margin  # Maximum y-coordinate before bottom margin
    
    for line_idx, line in enumerate(wrapped_lines):
        words = line.split()
        
        if align == 'center':
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (width - w) // 2
            draw.text((x, y), line, font=font, fill=fg_color)
            
        elif align == 'right':
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = width - w - margin
            draw.text((x, y), line, font=font, fill=fg_color)
            
        elif align == 'justify':
            if len(words) > 1:
                # Calculate word widths
                word_widths = [draw.textbbox((0, 0), word, font=font)[2] for word in words]
                total_words_width = sum(word_widths)
                total_space = max_text_width - total_words_width
                
                # Check if this is the last line of paragraph or last line overall
                is_last_line = (line_idx == len(wrapped_lines) - 1) or (y + line_height * 2 > max_height)
                max_reasonable_space = font.size * 1.5  # Adjust this for tighter/looser spacing
                
                if is_last_line or (total_space / (len(words)-1) > max_reasonable_space):
                    # Left-align for last lines or when spacing would be too wide
                    draw.text((margin, y), ' '.join(words), font=font, fill=fg_color)
                else:
                    # Justify with even spacing
                    space_between = total_space / (len(words)-1)
                    x = margin
                    for i, (word, word_width) in enumerate(zip(words, word_widths)):
                        draw.text((x, y), word, font=font, fill=fg_color)
                        if i < len(words)-1:
                            x += word_width + space_between
            else:
                # Single word - just left align
                draw.text((margin, y), line, font=font, fill=fg_color)
                
        else:  # left alignment
            draw.text((margin, y), line, font=font, fill=fg_color)
            
        y += line_height
    
    return img

def make_solution_image(sol, out_path, font_path):
    # Compose text block
    # Format solution and choice with a line break between them
    solution_text = sol.get('Solution', '').strip()
    choice_text = f"Choice: {sol['Choice']}" if sol.get('Choice') else ''
    # Add a line break after solution if choice exists
    if solution_text and choice_text:
        text = f"{solution_text}\n\n{choice_text}"
    else:
        text = solution_text or choice_text

    # Render text to image
    img = render_text_to_image(text, font_path=font_path)

    # Render tables (as classic grid below the solution)
    tables = sol.get('Table', [])
    # Inside make_solution_image, replace the existing "Render tables" block with this:

    if tables:
        from PIL import ImageDraw
        import io
        from bs4 import BeautifulSoup
        import math
        for table_html in tables:
            soup = BeautifulSoup(table_html, 'html.parser')

            # --- Parse table with merged cells (rowspan/colspan) ---
            grid = []  # 2D list of cell dicts: {text, rowspan, colspan, is_header, rendered}
            max_cols = 0
            trs = soup.find_all('tr')
            for tr in trs:
                row = []
                tds = tr.find_all(['td', 'th'])
                for td in tds:
                    cell_content = ''.join(str(x) for x in td.contents)
                    cell_text = BeautifulSoup(cell_content, 'html.parser').get_text("\n", strip=True)
                    rowspan = int(td.get('rowspan', 1))
                    colspan = int(td.get('colspan', 1))
                    is_header = td.name == 'th'
                    row.append({'text': cell_text, 'rowspan': rowspan, 'colspan': colspan, 'is_header': is_header, 'rendered': False})
                max_cols = max(max_cols, sum(cell['colspan'] for cell in row))
                grid.append(row)

            # Expand grid to 2D array with merged cells placed correctly
            table_matrix = []  # Each row is a list of cell dicts or None (for spanned cells)
            for row in grid:
                # Find the next available row in table_matrix
                r = len(table_matrix)
                if r == 0:
                    table_matrix.append([None] * max_cols)
                while len(table_matrix) <= r:
                    table_matrix.append([None] * max_cols)
                c = 0
                for cell in row:
                    # Find next empty col
                    while c < max_cols and table_matrix[r][c] is not None:
                        c += 1
                    # Place cell
                    for dr in range(cell['rowspan']):
                        while len(table_matrix) <= r + dr:
                            table_matrix.append([None] * max_cols)
                        for dc in range(cell['colspan']):
                            if dr == 0 and dc == 0:
                                table_matrix[r + dr][c + dc] = cell
                            else:
                                table_matrix[r + dr][c + dc] = None  # Mark as spanned
                    c += cell['colspan']

            # Remove empty rows (all None)
            table_matrix = [row for row in table_matrix if any(cell is not None for cell in row)]
            n_rows = len(table_matrix)
            n_cols = max_cols
            if n_rows == 0 or n_cols == 0:
                continue

            font = ImageFont.truetype(font_path, 28)
            cell_padding = 20
            row_spacing = 1.6

            # Calculate column widths (max width of any line in any cell in that col)
            col_widths = [0] * n_cols
            for row in table_matrix:
                for col_idx, cell in enumerate(row):
                    if cell is not None:
                        lines = cell['text'].split('\n')
                        max_line_width = max((font.getlength(line) for line in lines), default=0)
                        col_widths[col_idx] = max(col_widths[col_idx], int(max_line_width + 2 * cell_padding))

            # Calculate row heights (max lines in any cell in that row)
            row_heights = []
            for row in table_matrix:
                max_lines = 1
                for cell in row:
                    if cell is not None:
                        max_lines = max(max_lines, len(cell['text'].split('\n')))
                height = int(font.size * max_lines * row_spacing) + 10
                row_heights.append(height)

            table_width = sum(col_widths)
            table_height = sum(row_heights)

            table_img = Image.new('RGB', (table_width, table_height), color='white')
            draw = ImageDraw.Draw(table_img)

            # Draw grid and text, skipping spanned cells
            y = 0
            for row_idx, row in enumerate(table_matrix):
                x = 0
                for col_idx, cell in enumerate(row):
                    if cell is not None and not cell.get('rendered', False):
                        # Draw cell border for the merged area
                        span_w = sum(col_widths[col_idx:col_idx+cell['colspan']])
                        span_h = sum(row_heights[row_idx:row_idx+cell['rowspan']])
                        draw.rectangle([x, y, x + span_w, y + span_h], outline='black', width=2)
                        # Draw text centered in merged cell
                        cell_lines = cell['text'].split('\n')
                        total_text_height = len(cell_lines) * int(font.size * row_spacing)
                        start_y = y + (span_h - total_text_height) // 2
                        for idx2, line in enumerate(cell_lines):
                            bbox = draw.textbbox((0, 0), line, font=font)
                            text_w = bbox[2] - bbox[0]
                            text_x = x + (span_w - text_w) // 2
                            text_y = start_y + int(idx2 * font.size * row_spacing)
                            draw.text((text_x, text_y), line, font=font, fill='black')
                        # Mark all spanned cells as rendered
                        for dr in range(cell['rowspan']):
                            for dc in range(cell['colspan']):
                                if table_matrix[row_idx+dr][col_idx+dc] is not None:
                                    table_matrix[row_idx+dr][col_idx+dc]['rendered'] = True
                    x += col_widths[col_idx]
                y += row_heights[row_idx]

            # Combine table_img with main solution image
            new_img = Image.new('RGB', (img.width, img.height + table_img.height + 20), color='white')
            new_img.paste(img, (0, 0))
            new_img.paste(table_img, ((img.width - table_img.width) // 2, img.height + 10))
            img = new_img

    img.save(out_path)

def main():
    parser = argparse.ArgumentParser(description='Generate solution images from Solutions JSON')
    parser.add_argument('--json', type=str, required=True, help='Path to Solutions JSON')
    parser.add_argument('--outdir', type=str, default=None, help='Output directory (default: conversions/<upload_folder> at project root)')
    parser.add_argument('--font', type=str, default=None, help='Font path')
    parser.add_argument('--filename', type=str, default=None, help='Original Word document filename (for folder naming)')
    args = parser.parse_args()
    with open(args.json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    font_path = args.font or os.path.join(os.path.dirname(__file__), '../dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf')
    # Use --filename if provided, else fallback to JSON data
    filename = args.filename or data.get('filename', 'default')
    # Determine output directory: <project_root>/conversions/<upload_folder>
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    conversions_dir = os.path.join(project_root, 'conversions')
    upload_folder = os.path.splitext(os.path.basename(filename))[0] if filename else 'default_upload'
    outdir = args.outdir or os.path.join(conversions_dir, upload_folder)
    os.makedirs(outdir, exist_ok=True)
    print(f"Images will be saved in: {os.path.abspath(outdir)}")
    # Iterate over all sections in the JSON (skip 'filename' key)
    has_sections = any(isinstance(v, list) and section != 'filename' for section, v in data.items())
    for section, solutions in data.items():
        if section == 'filename':
            continue
        # If there are sections, create a subfolder for each section
        if has_sections:
            section_dir = os.path.join(outdir, section)
            os.makedirs(section_dir, exist_ok=True)
            target_dir = section_dir
        else:
            target_dir = outdir
        for sol in solutions:
            snum = sol.get('solution_number', 'unknown')
            out_path = os.path.join(target_dir, f'solution_{snum}.png')
            make_solution_image(sol, out_path, font_path)
            # print(f"Saved: {out_path}")

    # Zip the upload_folder and print the path
    import shutil
    zip_base = os.path.join(conversions_dir, upload_folder)
    zip_path = shutil.make_archive(zip_base, 'zip', outdir)
    print("===ZIP===")
    print(zip_path)

if __name__ == '__main__':
    main()
