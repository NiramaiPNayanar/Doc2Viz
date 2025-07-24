import os
import re
import json

def parse_cleaned_markdown(cleaned_md_path, extracted_images=None):
    with open(cleaned_md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # --- Custom: Extract image paths from Markdown and map to questions ---
    # Build a map: question number -> image paths found in markdown
    md_image_map = {}
    # Find all question numbers and their positions
    qnum_pattern = re.compile(r'<strong>(?:<[^>]+>)*\s*(\d+)\s*\.?(:?\s+[^<]*)?</strong>', re.IGNORECASE)
    qnum_matches = list(qnum_pattern.finditer(content))
    # Find all markdown images and their positions
    md_img_pattern = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
    md_img_matches = list(md_img_pattern.finditer(content))
    # For each image, find the closest preceding question number
    # def preprocess_md_image_path(img_path):
    #     # If the path is an absolute Windows path (starts with drive letter and colon), return as is
    #     import re
    #     if re.match(r'^[A-Za-z]:[\\/]', img_path):
    #         return img_path.strip()
    #     # Remove HTML tags (e.g., <em>, <strong>)
    #     img_path = re.sub(r'<[^>]+>', '', img_path)
    #     # Remove invisible unicode chars
    #     img_path = re.sub(r'[\u200c-\u206f]', '', img_path)
    #     # Remove whitespace and normalize slashes
    #     img_path = img_path.strip().replace('\\', '/').replace(' ', '')
    #     # Optionally, fix Windows drive letter if needed
    #     # If the path looks like D:Projects..., try to recover a valid path
    #     # Look for a media/image... pattern and reconstruct a relative path
    #     m = re.search(r'(media/[^\s)]+)', img_path)
    #     if m:
    #         img_path = os.path.join('output_test', m.group(1))
    #     return img_path

    # Always resolve image path to full path in the correct media folder (not media/media)
    visuals_json_path = os.path.join(os.path.dirname(cleaned_md_path), 'html_extraction', 'visuals.json')
    # Fix: Use media/media as the actual image directory
    media_dir = os.path.join(os.path.dirname(visuals_json_path), 'media', 'media')
    for img_match in md_img_matches:
        img_path = img_match.group(1)
        # Remove any 'media/' or 'media/media/' prefix, always use only the filename
        img_path_clean = img_path.replace('\\', '/').replace('..', '')
        img_path_clean = re.sub(r'^(media/)+', '', img_path_clean)
        img_path_clean = img_path_clean.replace('media/', '')
        filename = os.path.basename(img_path_clean)
        abs_img_path = os.path.abspath(os.path.join(media_dir, filename))
        img_pos = img_match.start()
        q_for_img = None
        for q_idx, q_match in enumerate(qnum_matches):
            if q_match.start() > img_pos:
                break
            q_for_img = int(q_match.group(1))
        if q_for_img is not None:
            # Only add if not already present for this question (deduplicate)
            q_key = str(q_for_img)
            if q_key not in md_image_map:
                md_image_map[q_key] = []
            if abs_img_path not in md_image_map[q_key]:
                md_image_map[q_key].append(abs_img_path)

    # If a visuals JSON file exists, load it and build a qnum->images/tables map
    visuals_map = {}
    visuals_common_contexts = []
    visuals_json_path = os.path.join(os.path.dirname(cleaned_md_path), 'html_extraction', 'visuals.json')
    media_dir = os.path.join(os.path.dirname(visuals_json_path), 'media')
    if os.path.exists(visuals_json_path):
        try:
            with open(visuals_json_path, 'r', encoding='utf-8') as vf:
                visuals_list = json.load(vf)
            def resolve_media_path(img_path):
                # If already absolute, return as is
                if os.path.isabs(img_path):
                    return img_path
                # Normalize slashes
                img_path = img_path.replace('\\', '/').replace('..', '')
                # Remove any leading './' or '.\'
                img_path = re.sub(r'^\./+', '', img_path)
                # Always join with .../media/media/filename, regardless of input
                filename = os.path.basename(img_path)
                return os.path.abspath(os.path.join(media_dir, 'media', filename))
            for entry in visuals_list:
                qnum = str(entry.get('question_number'))
                # Use 'images' and 'tables' keys (lowercase) as per visuals.json
                images = [resolve_media_path(p) for p in entry.get('images', [])]
                tables = entry.get('tables', [])
                if qnum == 'common' and 'context_text' in entry:
                    visuals_common_contexts.append({
                        'context_text': entry.get('context_text'),
                        'images': images,
                        'tables': tables
                    })
                else:
                    visuals_map[qnum] = {
                        'images': images,
                        'tables': tables
                    }
        except Exception as e:
            visuals_map = {}
    with open(cleaned_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all section headers (e.g., <strong>TEST -- I</strong>)
    section_pattern = re.compile(r'<strong>\s*TEST\s*[-–]+\s*([IVX1-9]+)\s*</strong>', re.IGNORECASE)
    section_matches = list(section_pattern.finditer(content))
    sections = []
    for idx, match in enumerate(section_matches):
        section_name = match.group(0)
        start = match.end()
        end = section_matches[idx+1].start() if idx+1 < len(section_matches) else len(content)
        section_content = content[start:end]
        sections.append((section_name, section_content))

    # If no section headers found, treat the whole file as one section
    if not sections:
        sections = [("", content)]

    all_sections = {}
    for section_name, section_content in sections:
        # Enhanced direction patterns to capture more variations
        plural_dir_pattern = re.compile(r'<em><strong>Directions? for questions? (\d+)(?: to | and )(\d+):?.*?</strong></em>', re.IGNORECASE)
        singular_dir_pattern = re.compile(r'<em><strong>Directions? for question (\d+):?.*?</strong></em>', re.IGNORECASE)

        # Find all direction blocks and map them to question numbers
        direction_blocks = []  # (start_q, end_q, dir_text, dir_full_text, dir_start, dir_end)
        for m in plural_dir_pattern.finditer(section_content):
            start_q = int(m.group(1))
            end_q = int(m.group(2)) if m.group(2) else start_q
            dir_start = m.start()
            # The direction ends at the next question number or next direction or end of section
            next_dir = plural_dir_pattern.search(section_content, m.end())
            next_sing_dir = singular_dir_pattern.search(section_content, m.end())
            next_q = re.search(r'<strong>(?:<[^>]+>)*\s*\d+\s*\.?(:?\s+[^<]*)?</strong>', section_content, re.IGNORECASE)
            nexts = [x for x in [next_dir, next_sing_dir, next_q] if x and x.start() > m.end()]
            if nexts:
                dir_end = min(x.start() for x in nexts)
            else:
                dir_end = len(section_content)
            dir_full_text = section_content[dir_start:dir_end].strip()
            dir_text = m.group(0)
            direction_blocks.append((start_q, end_q, dir_text, dir_full_text, dir_start, dir_end))
        for m in singular_dir_pattern.finditer(section_content):
            start_q = int(m.group(1))
            end_q = start_q
            dir_start = m.start()
            next_dir = plural_dir_pattern.search(section_content, m.end())
            next_sing_dir = singular_dir_pattern.search(section_content, m.end())
            next_q = re.search(r'<strong>(?:<[^>]+>)*\s*\d+\s*\.?(:?\s+[^<]*)?</strong>', section_content, re.IGNORECASE)
            nexts = [x for x in [next_dir, next_sing_dir, next_q] if x and x.start() > m.end()]
            if nexts:
                dir_end = min(x.start() for x in nexts)
            else:
                dir_end = len(section_content)
            dir_full_text = section_content[dir_start:dir_end].strip()
            dir_text = m.group(0)
            direction_blocks.append((start_q, end_q, dir_text, dir_full_text, dir_start, dir_end))

        # Sort by start_q, then by dir_start
        direction_blocks.sort(key=lambda x: (x[0], x[4]))

        # Process extracted images for direction blocks (common data)
        if extracted_images:
            for img_info in extracted_images:
                # Skip images already assigned
                if 'assigned' in img_info and img_info['assigned']:
                    continue
                
                surrounding_text = img_info.get('surrounding_text', '')
                
                # Check if this image belongs to a direction block
                for start_q, end_q, dir_text, dir_full_text, dir_start, dir_end in direction_blocks:
                    # Remove HTML tags for better matching
                    plain_dir_text = re.sub(r'<[^>]+>', '', dir_text)
                    
                    # Check if the surrounding text contains direction indicators
                    direction_indicators = [
                        "Directions",
                        "DIRECTIONS",
                        "directions for",
                        "Directions for",
                        plain_dir_text
                    ]
                    
                    if any(indicator in surrounding_text for indicator in direction_indicators):
                        # Mark this image for the questions in this direction block
                        img_info['assigned'] = True
                        img_info['direction_block'] = (start_q, end_q)
                        break

        # Build main_common_map and sub_common_map
        main_common_map = {}
        sub_common_map = {}
        for start_q, end_q, dir_text, dir_full_text, dir_start, dir_end in direction_blocks:
            for q in range(start_q, end_q + 1):
                if q not in main_common_map:
                    main_common_map[q] = dir_full_text
                else:
                    # If already filled, put in sub_common_map
                    sub_common_map[q] = dir_full_text

        # Fallback: If no direction blocks, use text before first question as main_common_data for all
        question_split = list(re.finditer(r'<strong>\d+\.</strong>', section_content))
        fallback_main_common = ''
        if question_split:
            first_q_start = question_split[0].start()
            fallback_main_common = section_content[:first_q_start].strip()
        else:
            fallback_main_common = section_content.strip()
            
        # Prepare a map of images for common data
        main_common_images = {}
        sub_common_images = {}
        
        # Process extracted images for common data
        if extracted_images:
            for img_info in extracted_images:
                if 'assigned' in img_info and 'direction_block' in img_info:
                    start_q, end_q = img_info['direction_block']
                    img_path = img_info.get('path', '')
                    
                    # Add this image to all questions in the direction block
                    for q in range(start_q, end_q + 1):
                        if q in main_common_map:
                            if q not in main_common_images:
                                main_common_images[q] = []
                            main_common_images[q].append(img_path)
                        elif q in sub_common_map:
                            if q not in sub_common_images:
                                sub_common_images[q] = []
                            sub_common_images[q].append(img_path)

        def remove_questions_and_options_from_common(text):
            # Remove all question lines: <strong>n.</strong> or <strong>n. ...</strong>
            text = re.sub(r'<strong>\s*\d+\s*\.?[^<]*?</strong>.*?(?=(<strong>|$))', '', text, flags=re.DOTALL)
            # Remove all options: lines starting with (A)-(E) or [A-E] etc
            text = re.sub(r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*.*$', '', text, flags=re.MULTILINE)
            return text

        def get_main_common_data(qnum):
            if qnum in main_common_map:
                raw = main_common_map[qnum]
            else:
                raw = fallback_main_common if fallback_main_common else ''
            # Preprocess to exclude questions and options
            return remove_questions_and_options_from_common(raw).strip()
            
        def get_main_common_images(qnum):
            if qnum in main_common_images:
                return main_common_images[qnum]
            return []

        def get_sub_common_data(qnum):
            raw = sub_common_map.get(qnum, '')
            return remove_questions_and_options_from_common(raw).strip()
            
        def get_sub_common_images(qnum):
            if qnum in sub_common_images:
                return sub_common_images[qnum]
            return []

        # Split into questions by <strong>n.</strong> and robustly detect question numbers
        # Robust question pattern: allow optional whitespace, bold, italics, possible HTML noise, and also match <strong>9. SOUND</strong>
        question_pattern = re.compile(r'<strong>(?:<[^>]+>)*\s*(\d+)\s*\.?(:?\s+[^<]*)?</strong>', re.IGNORECASE)
        question_matches = list(question_pattern.finditer(section_content))
        questions = []

        for idx, match in enumerate(question_matches):
            qnum = int(match.group(1))
            q_start = match.start()
            q_end = question_matches[idx+1].start() if idx+1 < len(question_matches) else len(section_content)
            qbody = section_content[q_start:q_end]

            # Initial assignment of common data
            main_common_data = get_main_common_data(qnum)
            sub_common_data = get_sub_common_data(qnum)
            main_common_images = get_main_common_images(qnum)
            sub_common_images = get_sub_common_images(qnum)

            # Merge images from visuals.json and Markdown, deduplicated
            images = []
            q_key = str(qnum)
            if q_key in visuals_map:
                images.extend(visuals_map[q_key].get('images', []))
            if q_key in md_image_map:
                images.extend(md_image_map[q_key])
            # Deduplicate, preserve order
            images = list(dict.fromkeys(images))

            # Only take tables from visuals.json, ignore tables in markdown/HTML
            # import logging
            # logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(message)s')
            tables = []
            if q_key in visuals_map:
                # logging.debug(f"Q{q_key}: Assigning tables from visuals.json: {visuals_map[q_key].get('tables', [])}")
                tables.extend(visuals_map[q_key].get('tables', []))
            # logging.debug(f"Q{q_key}: Final tables for question: {tables}")

            # ...existing code for extracting options, question text, etc...
            # Remove any direction block from the question text (if present)
            for _, _, dir_text, dir_full_text, dir_start, dir_end in direction_blocks:
                if dir_text in qbody:
                    qbody = qbody.replace(dir_full_text, '').replace(dir_text, '').strip()

            # Remove the question number and any trailing punctuation/word from the start of the question
            qbody = re.sub(r'^<strong>(?:<[^>]+>)*\s*\d+\s*\.?(:?\s+[^<]*)?</strong>\s*', '', qbody, flags=re.IGNORECASE)
            norm_qbody = re.sub(r'^[> \t]+', '', qbody, flags=re.MULTILINE)

            # Extract options (all, not just last)
            options = []
            option_regex = re.compile(
                r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*((?:.*?)(?=^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]]|^\s*$|\Z))',
                re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
            for m in option_regex.finditer(norm_qbody):
                letter = m.group(1).upper()
                text = m.group(2).replace('\n', ' ').replace('  ', ' ').strip()
                text = re.sub(r'^[> \t]+', '', text, flags=re.MULTILINE)
                text = re.sub(r'\s+', ' ', text).strip()
                options.append(f"({letter}) {text}")

            def remove_options_from_text(text):
                return option_regex.sub('', text)



            numbered_options_pattern = re.compile(r'\((\d+)\)')
            numbered_options = list(numbered_options_pattern.finditer(norm_qbody))
            numbered_opts = []
            if numbered_options and len(numbered_options) > 1:
                # There are at least two numbered options, treat as inline options
                qtext = norm_qbody[:numbered_options[0].start()].strip()
                for idx, m in enumerate(numbered_options):
                    start = m.start()
                    end = numbered_options[idx+1].start() if idx+1 < len(numbered_options) else len(norm_qbody)
                    opt_text = norm_qbody[start:end].strip()
                    # Remove newlines and extra spaces
                    opt_text = re.sub(r'\s+', ' ', opt_text)
                    numbered_opts.append(opt_text)
                # Replace options with this new list
                options = numbered_opts
            else:
                # Fallback to old extraction
                first_option_match = option_regex.search(norm_qbody)
                if first_option_match:
                    qtext = norm_qbody[:first_option_match.start()].strip()
                else:
                    qtext = norm_qbody.strip()

            # Remove any direction block from the question text (if present)
            for _, _, dir_text, dir_full_text, dir_start, dir_end in direction_blocks:
                if dir_text in qtext:
                    qtext = qtext.replace(dir_full_text, '').replace(dir_text, '').strip()

            # Remove any image paths from the question text (e.g., ![...](...))
            qtext = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', qtext)
            # Also remove any leftover whitespace from image removal
            qtext = re.sub(r'\s+', ' ', qtext).strip()

            # Clean up any leftover newlines or excessive whitespace
            qtext = re.sub(r'\n{3,}', '\n\n', qtext)
            qtext = re.sub(r'^\s+', '', qtext)
            qtext = re.sub(r'\s+$', '', qtext)
            qtext = qtext.strip()

            # Remove newlines and render HTML tags from main_common_data, sub_common_data, Question, and Options
            from html import unescape
            from bs4 import BeautifulSoup

            def clean_and_render_html(s):
                if not isinstance(s, str):
                    return s
                s = s.replace('\n', ' ')
                # Unescape HTML entities
                s = unescape(s)
                # Render HTML tags to plain text (preserve bold/italic as unicode if possible)
                soup = BeautifulSoup(s, 'html.parser')
                # Replace <strong> and <b> with bold, <em> and <i> with italic, <u> with underline
                for tag in soup.find_all(['strong', 'b']):
                    tag.string = f"\u2062{tag.get_text()}\u2062"  # Use invisible separator for bold
                for tag in soup.find_all(['em', 'i']):
                    tag.string = f"\u2063{tag.get_text()}\u2063"  # Use invisible separator for italic
                for tag in soup.find_all('u'):
                    tag.string = f"_{tag.get_text()}_"
                # Get text only
                text = soup.get_text(separator=' ', strip=True)
                # Remove unwanted backslash before dot in roman/numbered points (e.g., II\.)
                text = re.sub(r'(\b[A-Z]+)\\\.', r'\1.', text)
                text = re.sub(r'(\b\d+)\\\.', r'\1.', text)
                return text

            questions.append({
                'main_common_data': clean_and_render_html(main_common_data or ''),
                'sub_common_data': clean_and_render_html(sub_common_data or ''),
                'Question Number': str(qnum),
                'Question': clean_and_render_html(qtext or ''),
                'Options': [clean_and_render_html(opt) for opt in options] if options else [],
                'Table': tables if tables else [],
                'Image': images if images else []
            })
            # Do NOT add any images from visuals.json, extracted_images, or common data images to the question's Image field
        
        # Second pass: process cross-question directions
        # For each question, check if it contains directions for future questions
        direction_section_map = {}
        for q in questions:
            qnum = int(q['Question Number'])
            direction = q.get('direction_in_body', '')
            
            if direction:
                # Find which question this direction applies to
                dir_match = re.search(r'<strong><em>Directions? for questions? (\d+)(?:(?: to | and )(\d+))?:?', direction, re.IGNORECASE)
                if dir_match:
                    next_q_start = int(dir_match.group(1))
                    next_q_end = int(dir_match.group(2)) if dir_match.group(2) else next_q_start
                    
                    # Store for all questions in the range
                    for target_q in range(next_q_start, next_q_end + 1):
                        direction_section_map[target_q] = direction
            
            # Clean up temporary field
            if 'direction_in_body' in q:
                del q['direction_in_body']
        
        # Apply the directions to the right questions
        for q in questions:
            qnum = int(q['Question Number'])
            if qnum in direction_section_map:
                q['sub_common_data'] = direction_section_map[qnum]
        
        # Section name for output (e.g., TEST - I)
        section_label = re.sub(r'<.*?>', '', section_name).replace('--', '-').strip() if section_name else ''
        all_sections[section_label] = {
            'Data': {
                'questions': questions
            }
        }
        
    # Compose the JSON structure
    data = {
        'filename': os.path.basename(cleaned_md_path),
        'Content': all_sections
    }
    
    # Map extracted images to the appropriate questions or common data sections
    if extracted_images:
        data = map_images_to_content(data, extracted_images)
        
    return data

def map_images_to_content(data, extracted_images):
    """
    Map extracted images to the appropriate questions or common data sections
    Args:
        data: JSON data structure
        extracted_images: List of extracted images with position information
    Returns:
        Updated JSON data with images mapped to the right fields
    """
    if not extracted_images:
        return data
        
    # Make a copy to avoid modifying the original list
    remaining_images = extracted_images.copy()
    
    # First pass: map images to specific questions based on identifiers
    for section_name, section_data in data['Content'].items():
        questions = section_data['Data']['questions']
        
        for question in questions:
            qnum = question['Question Number']
            question_identifiers = [
                f"{qnum}.",
                f"Question {qnum}",
                f"question {qnum}",
                f"Q{qnum}",
                f"Q.{qnum}",
                f"Q. {qnum}"
            ]
            
            # Find images for this question
            question_images = []
            i = 0
            while i < len(remaining_images):
                img_info = remaining_images[i]
                surrounding_text = img_info.get('surrounding_text', '')
                
                if any(identifier in surrounding_text for identifier in question_identifiers):
                    question_images.append(img_info.get('path', ''))
                    remaining_images.pop(i)
                else:
                    i += 1
            
            # Add found images to the question
            if question_images:
                if 'Image' not in question:
                    question['Image'] = []
                question['Image'].extend(question_images)
    
    # Second pass: map remaining images to common data sections
    for section_name, section_data in data['Content'].items():
        questions = section_data['Data']['questions']
        
        direction_indicators = [
            "Directions",
            "DIRECTIONS",
            "directions for",
            "Directions for"
        ]
        
        # Group questions by main_common_data
        common_data_groups = {}
        for question in questions:
            main_common = question.get('main_common_data', '')
            if main_common:
                if main_common not in common_data_groups:
                    common_data_groups[main_common] = []
                common_data_groups[main_common].append(question)
        
        # Map images to common data groups
        i = 0
        while i < len(remaining_images):
            img_info = remaining_images[i]
            surrounding_text = img_info.get('surrounding_text', '')
            
            # Try to match to direction blocks
            matched = False
            if any(indicator in surrounding_text for indicator in direction_indicators):
                for common_data, questions_group in common_data_groups.items():
                    if any(indicator in common_data for indicator in direction_indicators):
                        # This image belongs to this common data group
                        img_path = img_info.get('path', '')
                        for question in questions_group:
                            if 'Image' not in question:
                                question['Image'] = []
                            question['Image'].append(img_path)
                        matched = True
                        break
            
            if matched:
                remaining_images.pop(i)
            else:
                i += 1
    
    # Third pass: remaining images - assign to all questions as fallback
    if remaining_images:
        for section_name, section_data in data['Content'].items():
            questions = section_data['Data']['questions']
            
            for img_info in remaining_images:
                img_path = img_info.get('path', '')
                if img_path:
                    for question in questions:
                        if 'Image' not in question:
                            question['Image'] = []
                        question['Image'].append(img_path)
    
    return data

def main():
    cleaned_md_path = 'output_test/cleaned.md'  # Adjust as needed
    output_json_path = cleaned_md_path.replace('.md', '_sections.json')
    data = parse_cleaned_markdown(cleaned_md_path, None)

    # Final pass: ensure consistency across all questions and sections


    for section_name, section_data in data['Content'].items():
        questions = section_data['Data']['questions']

        # Generalise: Clean all main_common_data and sub_common_data fields to remove embedded questions/options
        def remove_questions_and_options_from_common(text):
            # Remove all question lines: <strong>n.</strong> or <strong>n. ...</strong>
            text = re.sub(r'<strong>\s*\d+\s*\.?[^<]*?</strong>.*?(?=(<strong>|$))', '', text, flags=re.DOTALL)
            # Remove all options: lines starting with (A)-(E) or [A-E] etc
            text = re.sub(r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*.*$', '', text, flags=re.MULTILINE)
            return text

        for q in questions:
            if q['main_common_data']:
                cleaned_main = remove_questions_and_options_from_common(q['main_common_data']).strip()
                q['main_common_data'] = cleaned_main
            if q['sub_common_data']:
                cleaned_sub = remove_questions_and_options_from_common(q['sub_common_data']).strip()
                q['sub_common_data'] = cleaned_sub

        # Clean up any empty fields and ensure all questions have at least an empty string
        for q in questions:
            if not q['Question']:
                q['Question'] = ""
            if not q['sub_common_data']:
                q['sub_common_data'] = ""

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cleaned_md_path = sys.argv[1]
    else:
        cleaned_md_path = 'modules/output_test/cleaned.md'
    def main_entry():
        data = parse_cleaned_markdown(cleaned_md_path, None)
        # Final pass: ensure consistency across all questions and sections
        for section_name, section_data in data['Content'].items():
            questions = section_data['Data']['questions']
            # ... (rest of main logic unchanged) ...
        output_json_path = cleaned_md_path.replace('.md', '_sections.json')
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    main_entry()
