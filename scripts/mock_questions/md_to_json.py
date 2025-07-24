import os
import re
import json

def parse_cleaned_markdown(cleaned_md_path, extracted_images=None):
    with open(cleaned_md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # (Markdown image extraction disabled; only visuals.json will be used for images/tables)

    # If a visuals JSON file exists, load it and build a qnum->images/tables map
    visuals_map = {}
    visuals_common_contexts = []
    visuals_json_path = os.path.join(os.path.dirname(cleaned_md_path), 'html_extraction', 'visuals.json')
    if os.path.exists(visuals_json_path):
        try:
            with open(visuals_json_path, 'r', encoding='utf-8') as vf:
                visuals_list = json.load(vf)
            for entry in visuals_list:
                qnum = str(entry.get('question_number'))
                if qnum == 'common' and 'context_text' in entry:
                    visuals_common_contexts.append({
                        'context_text': entry['context_text'],
                        'images': entry.get('images', []),
                        'tables': entry.get('tables', [])
                    })
                else:
                    visuals_map[qnum] = {
                        'images': entry.get('images', []),
                        'tables': entry.get('tables', [])
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
            # Do NOT remove lines starting with (A)-(E) or [A-E] etc in common data; only remove them from question body.
            # So, for common data, we keep all such lines.
            # text = re.sub(r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*.*$', '', text, flags=re.MULTILINE)
            # Remove table-like blocks: lines with 3+ consecutive spaces (likely table rows)
            text = re.sub(r'^(?=.*\s{3,}).*$', '', text, flags=re.MULTILINE)
            # Remove blocks of 2+ lines with mostly numbers/spaces/percents (table data)
            text = re.sub(r'((?:^([ \d%\-\|\.]*)$\n?){2,})', '', text, flags=re.MULTILINE)
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
        # Updated regex: capture question number and any word after the dot (e.g., SOUND)
        question_pattern = re.compile(r'<strong>(?:<[^>]+>)*\s*(\d+)\s*\.\s*([^<\n]*)?</strong>', re.IGNORECASE)
        question_matches = list(question_pattern.finditer(section_content))
        questions = []

        # --- Pass 1: Build all question dicts with empty images/tables ---
        cleaned_main_common_data_map = {}
        question_dicts = []
        for idx, match in enumerate(question_matches):
            qnum = int(match.group(1))
            main_common_data = get_main_common_data(qnum)
            # Clean and lower for partial matching
            cleaned = re.sub(r'\s+', ' ', main_common_data.strip()).lower()
            cleaned_main_common_data_map[qnum] = cleaned

            q_start = match.start()
            q_end = question_matches[idx+1].start() if idx+1 < len(question_matches) else len(section_content)
            qbody = section_content[q_start:q_end]

            # Initial assignment of common data
            sub_common_data = get_sub_common_data(qnum)

            # Remove the question header from the body
            qbody = re.sub(r'^<strong>(?:<[^>]+>)*\s*\d+\s*\.\s*([^<\n]*)?</strong>\s*', '', qbody, flags=re.IGNORECASE)
            norm_qbody = re.sub(r'^[> \t]+', '', qbody, flags=re.MULTILINE)

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

            # Robustly extract all lines between the question number and the first option (multi-line safe)
            first_option_match = option_regex.search(norm_qbody)
            if first_option_match:
                qtext = norm_qbody[:first_option_match.start()].strip()
            else:
                qtext = norm_qbody.strip()

            # If the question header had a word (e.g., SOUND), and the body is empty, use that as the question text
            header_word = (match.group(2) or '').strip()
            if not qtext and header_word:
                qtext = header_word

            for _, _, dir_text, dir_full_text, dir_start, dir_end in direction_blocks:
                if dir_text in qtext:
                    qtext = qtext.replace(dir_full_text, '').replace(dir_text, '').strip()

            # Remove Markdown image links, HTML <img> tags, and media paths from question text
            qtext = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', qtext)
            qtext = re.sub(r'<img[^>]*src=["\']?media/[^>]*>', '', qtext, flags=re.IGNORECASE)
            qtext = re.sub(r'media/[^\s)>"]+', '', qtext, flags=re.IGNORECASE)
            qtext = re.sub(r'\s+', ' ', qtext).strip()
            qtext = re.sub(r'\n{3,}', '\n\n', qtext)
            qtext = re.sub(r'^\s+', '', qtext)
            qtext = re.sub(r'\s+$', '', qtext)
            qtext = qtext.strip()

            from html import unescape
            from bs4 import BeautifulSoup

            def clean_and_render_html(s):
                if not isinstance(s, str):
                    return s
                s = s.replace('\n', ' ')
                s = unescape(s)
                # Remove Markdown/HTML image tags with media/ or similar paths
                s = re.sub(r'!\[[^\]]*\]\(([^)]*media/[^)]*)\)', '', s)
                s = re.sub(r'<img[^>]+src=["\']?[^>]*media/[^>]*>', '', s, flags=re.IGNORECASE)
                s = re.sub(r'!\[[^\]]*\]\(([^)]*\.(?:png|jpg|jpeg|gif|bmp|svg))\)', '', s, flags=re.IGNORECASE)
                s = re.sub(r'<img[^>]+src=["\']?[^>]*\.(?:png|jpg|jpeg|gif|bmp|svg)[^>]*>', '', s, flags=re.IGNORECASE)
                s = re.sub(r'media/[^\s)>\"]+', '', s, flags=re.IGNORECASE)
                # DO NOT strip <strong> or <b> tags for the Question field (let renderer handle it)
                return s

            qdict = {
                'main_common_data': clean_and_render_html(main_common_data or ''),
                'sub_common_data': clean_and_render_html(sub_common_data or ''),
                'Question Number': str(qnum),
                'Question': clean_and_render_html(qtext or ''),
                'Options': [clean_and_render_html(opt) for opt in options] if options else [],
                'Table': [],  # to be filled from visuals.json
                'Image': []   # to be filled from visuals.json
            }
            question_dicts.append(qdict)

        # --- Pass 2: Assign images/tables from visuals.json ---
        # Build a map from question number to question dict
        qnum_to_qdict = {q['Question Number']: q for q in question_dicts}

        # 1. Assign direct question_number visuals
        for qnum_str, v in visuals_map.items():
            if qnum_str == 'common':
                continue
            if qnum_str in qnum_to_qdict:
                qd = qnum_to_qdict[qnum_str]
                if v.get('images'):
                    qd['Image'].extend(v['images'])
                if v.get('tables'):
                    qd['Table'].extend(v['tables'])
                # print(f"Assigning images to Q{qnum_str} from visuals.json: {v.get('images',[])}")
                # print(f"Assigning tables to Q{qnum_str} from visuals.json: {v.get('tables',[])}")

        # 2. Assign 'common' visuals by context matching
        # For each visuals_common_contexts entry, match its context_text to main_common_data (even partial/first few words)
        for entry in visuals_common_contexts:
            context_text = entry.get('context_text')
            if not isinstance(context_text, str):
                context_text = ''
            context_text = context_text.strip()
            images = entry.get('images', [])
            tables = entry.get('tables', [])
            if not context_text:
                continue
            # Try to match to any question whose main_common_data starts with or contains the context_text (first few words)
            context_words = context_text.split()
            if not context_words:
                continue
            context_prefix = ' '.join(context_words[:min(5, len(context_words))]).lower()
            for qd in question_dicts:
                main_common = qd.get('main_common_data')
                if not isinstance(main_common, str):
                    main_common = ''
                main_common = main_common.strip().lower()
                # Match if context_prefix is in main_common, or first 5 words of main_common match context_prefix
                main_common_prefix = ' '.join(main_common.split()[:min(5, len(main_common.split()))])
                if context_prefix and (context_prefix in main_common or main_common_prefix == context_prefix):
                    if images:
                        qd['Image'].extend(images)
                    if tables:
                        qd['Table'].extend(tables)
                    # print(f"Assigning common images/tables to Q{qd['Question Number']} by context match: {images}, {tables}")

        questions = question_dicts
        
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
