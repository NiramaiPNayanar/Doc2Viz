import re
import logging
import os
import json
from html import unescape 

# Assuming normalize_and_strip_lines is imported or defined in the same scope
# If md_cleaner is a separate module, you might need:
# from md_cleaner import normalize_and_strip_lines 
# For this example, I'll include it directly for self-containment, but it's better to import.

# --- NEW UTILITY FUNCTION FOR MULTI-LINE TEXT CLEANING (DUPLICATED FOR EXAMPLE, BETTER TO IMPORT) ---
def normalize_and_strip_lines(text):
    """
    Normalizes line endings, reduces excessive newlines, and strips
    whitespace from each line, preserving multi-line structure.
    This function replaces common flattening operations (e.g., re.sub(r'\s+', ' ', text)).
    """
    if not isinstance(text, str):
        return text
    text = re.sub(r'\r\n|\r', '\n', text)  # Normalize line endings (CRLF to LF, CR to LF)
    text = re.sub(r'\n{3,}', '\n\n', text)  # Replace 3+ newlines with exactly 2
    # Strip leading/trailing whitespace from each line while preserving line breaks
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip() # Final strip of the whole block


def parse_cleaned_markdown(cleaned_md_path, extracted_images=None):
    with open(cleaned_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

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
            logging.error(f"Failed to load or parse visuals.json: {e}")
    
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
        # Find first question by either <strong>n.</strong> or plain/escaped n. or n\.
        html_q_match = re.search(r'<strong>\s*\d+\s*\.', section_content)
        plain_q_match = re.search(r'^(?:\\)?\d+\\?\.', section_content, re.MULTILINE)
        if html_q_match and plain_q_match:
            first_q_start = min(html_q_match.start(), plain_q_match.start())
        elif html_q_match:
            first_q_start = html_q_match.start()
        elif plain_q_match:
            first_q_start = plain_q_match.start()
        else:
            first_q_start = None
        if first_q_start is not None:
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
            # Preprocess to exclude questions and options, then normalize lines
            return normalize_and_strip_lines(remove_questions_and_options_from_common(raw))
            
        def get_main_common_images(qnum):
            if qnum in main_common_images:
                return main_common_images[qnum]
            return []

        def get_sub_common_data(qnum):
            raw = sub_common_map.get(qnum, '')
            return normalize_and_strip_lines(remove_questions_and_options_from_common(raw))
            
        def get_sub_common_images(qnum):
            if qnum in sub_common_images:
                return sub_common_images[qnum]
            return []
            
        # Split into questions by both <strong>n.</strong> and plain numbered questions (e.g., 1. ...)
        # Robust question pattern: allow optional whitespace, bold, italics, possible HTML noise, and also match <strong>9. SOUND</strong>
        # Updated regex: capture question number and any word after the dot (e.g., SOUND)
        html_question_pattern = re.compile(r'<strong>(?:<[^>]+>)*\s*(\d+)\s*\.\s*([^<\n]*)?</strong>', re.IGNORECASE)
        # Also match escaped numbers like 1\.
        # Accepts: 1.  1\.  (with or without backslash)
        # New: plain_question_pattern also handles the bolding within itself for consistency.
        plain_question_pattern = re.compile(r'^(?:\\)?(\d+)\\?\.\s*(.*)$', re.MULTILINE)

        # Find all matches for both patterns
        html_matches = list(html_question_pattern.finditer(section_content))
        plain_matches = list(plain_question_pattern.finditer(section_content))

        # Merge and sort all matches by their start position
        all_matches = [(m.start(), m, 'html') for m in html_matches] + [(m.start(), m, 'plain') for m in plain_matches]
        all_matches.sort(key=lambda x: x[0])

        questions = []
        cleaned_main_common_data_map = {}
        question_dicts = []
        for idx, (match_start, match, match_type) in enumerate(all_matches):
            if match_type == 'html':
                qnum = int(match.group(1))
                header_word = (match.group(2) or '').strip()
            else:
                qnum = int(match.group(1))
                header_word = (match.group(2) or '').strip()

            main_common_data = get_main_common_data(qnum)
            # For `cleaned_main_common_data_map`, if it's for partial matching, lowercasing and single space is fine.
            cleaned_main_common_data_map[qnum] = re.sub(r'\s+', ' ', main_common_data.strip()).lower() 

            q_start = match.start()
            q_end = all_matches[idx+1][0] if idx+1 < len(all_matches) else len(section_content)
            qbody = section_content[q_start:q_end]

            # Initial assignment of common data
            sub_common_data = get_sub_common_data(qnum)

            # Remove the question header from the body
            if match_type == 'html':
                qbody = re.sub(r'^<strong>(?:<[^>]+>)*\s*\d+\s*\.\s*([^<\n]*)?</strong>\s*', '', qbody, flags=re.IGNORECASE)
            else:
                qbody = re.sub(r'^\d+\.\s*.*', '', qbody, flags=re.IGNORECASE)
            norm_qbody = re.sub(r'^[> \t]+', '', qbody, flags=re.MULTILINE)

            # Track seen options to prevent duplicates
            seen_options = set()
            options = []
            option_regex = re.compile(
                r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*((?:.*?)(?=^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]]|^\s*$|\Z))',
                re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
            for m in option_regex.finditer(norm_qbody):
                letter = m.group(1).upper()
                if letter in seen_options:
                    continue  # Skip duplicate options
                seen_options.add(letter)
                
                # Preserve line breaks within options but normalize whitespace within each line
                text = m.group(2)
                # Split into lines and process each line
                lines = [line.strip() for line in text.split('\n')]
                # Remove empty lines and join with newlines
                text = '\n'.join(line for line in lines if line)
                # Remove blockquote characters
                text = re.sub(r'^[> \t]+', '', text, flags=re.MULTILINE)
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
            if not qtext and header_word:
                qtext = header_word

            for _, _, dir_text, dir_full_text, dir_start, dir_end in direction_blocks:
                if dir_text in qtext:
                    qtext = qtext.replace(dir_full_text, '').replace(dir_text, '').strip()

            # Remove Markdown image links, HTML <img> tags, and media paths from question text
            qtext = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', qtext)
            qtext = re.sub(r'<img[^>]*src=["\']?media/[^>]*>', '', qtext, flags=re.IGNORECASE)
            qtext = re.sub(r'media/[^\s)>\"]+', '', qtext, flags=re.IGNORECASE)
            
            qtext = normalize_and_strip_lines(qtext)

            def clean_and_render_html_for_dict_values(s): 
                if not isinstance(s, str):
                    return s
                s = unescape(s)
                # Remove Markdown/HTML image tags with media/ or similar paths
                s = re.sub(r'!\[[^\]]*\]\(([^)]*media/[^)]*)\)', '', s)
                s = re.sub(r'<img[^>]+src=["\']?[^>]*media/[^>]*>', '', s, flags=re.IGNORECASE)
                s = re.sub(r'!\[[^\]]*\]\(([^)]*\.(?:png|jpg|jpeg|gif|bmp|svg))\)', '', s, flags=re.IGNORECASE)
                s = re.sub(r'<img[^>]+src=["\']?[^>]*\.(?:png|jpg|jpeg|gif|bmp|svg)[^>]*>', '', s, flags=re.IGNORECASE)
                s = re.sub(r'media/[^\s)>"]+', '', s, flags=re.IGNORECASE)
                return s

            qdict = {
                'main_common_data': normalize_and_strip_lines(clean_and_render_html_for_dict_values(main_common_data or '')),
                'sub_common_data': normalize_and_strip_lines(clean_and_render_html_for_dict_values(sub_common_data or '')),
                'Question Number': str(qnum),
                'Question': normalize_and_strip_lines(clean_and_render_html_for_dict_values(qtext or '')),
                'Options': [normalize_and_strip_lines(opt.replace('\n', ' ')) for opt in options] if options else [], 
                'Table': [],
                'Image': []
            }
            question_dicts.append(qdict)

        # --- Pass 2: Assign images/tables from visuals.json ---
        qnum_to_qdict = {q['Question Number']: q for q in question_dicts}

        for qnum_str, v in visuals_map.items():
            if qnum_str == 'common':
                continue
            if qnum_str in qnum_to_qdict:
                qd = qnum_to_qdict[qnum_str]
                if v.get('images'):
                    qd['Image'].extend(v['images'])
                if v.get('tables'):
                    qd['Table'].extend(v['tables'])
                logging.debug(f"Assigning images to Q{qnum_str} from visuals.json: {v.get('images',[])}")
                logging.debug(f"Assigning tables to Q{qnum_str} from visuals.json: {v.get('tables',[])}")

        for entry in visuals_common_contexts:
            context_text = entry.get('context_text')
            if not isinstance(context_text, str):
                context_text = ''
            context_text = context_text.strip()
            images = entry.get('images', [])
            tables = entry.get('tables', [])
            if not context_text:
                continue
            context_words = context_text.split()
            if not context_words:
                continue
            context_prefix = ' '.join(context_words[:min(5, len(context_words))]).lower()
            for qd in question_dicts:
                main_common = qd.get('main_common_data')
                if not isinstance(main_common, str):
                    main_common = ''
                main_common = main_common.strip().lower()
                main_common_prefix = ' '.join(main_common.split()[:min(5, len(main_common.split()))])
                if context_prefix and (context_prefix in main_common or main_common_prefix == context_prefix):
                    if images:
                        qd['Image'].extend(images)
                    if tables:
                        qd['Table'].extend(tables)
                    logging.debug(f"Assigning common images/tables to Q{qd['Question Number']} by context match: {images}, {tables}")

        questions = question_dicts
        
        # Second pass: process cross-question directions
        direction_section_map = {}
        for q in questions:
            qnum = int(q['Question Number'])
            direction = q.get('direction_in_body', '')
            
            if direction:
                dir_match = re.search(r'<strong><em>Directions? for questions? (\d+)(?:(?: to | and )(\d+))?:?', direction, re.IGNORECASE)
                if dir_match:
                    next_q_start = int(dir_match.group(1))
                    next_q_end = int(dir_match.group(2)) if dir_match.group(2) else next_q_start
                    
                    for target_q in range(next_q_start, next_q_end + 1):
                        direction_section_map[target_q] = direction
            
            if 'direction_in_body' in q:
                del q['direction_in_body']
        
        for q in questions:
            qnum = int(q['Question Number'])
            if qnum in direction_section_map:
                q['sub_common_data'] = normalize_and_strip_lines(direction_section_map[qnum])
        
        section_label = re.sub(r'<.*?>', '', section_name).replace('--', '-').strip() if section_name else ''
        all_sections[section_label] = {
            'Data': {
                'questions': questions
            }
        }
        
    data = {
        'filename': os.path.basename(cleaned_md_path),
        'Content': all_sections
    }
    
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
        
    remaining_images = extracted_images.copy()
    
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
            
            if question_images:
                if 'Image' not in question:
                    question['Image'] = []
                question['Image'].extend(question_images)
    
    for section_name, section_data in data['Content'].items():
        questions = section_data['Data']['questions']
        
        direction_indicators = [
            "Directions",
            "DIRECTIONS",
            "directions for",
            "Directions for"
        ]
        
        common_data_groups = {}
        for question in questions:
            main_common = question.get('main_common_data', '')
            if main_common:
                if main_common not in common_data_groups:
                    common_data_groups[main_common] = []
                common_data_groups[main_common].append(question)
        
        i = 0
        while i < len(remaining_images):
            img_info = remaining_images[i]
            surrounding_text = img_info.get('surrounding_text', '')
            
            matched = False
            if any(indicator in surrounding_text for indicator in direction_indicators):
                for common_data, questions_group in common_data_groups.items():
                    if any(indicator in common_data for indicator in direction_indicators):
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
    logging.basicConfig(level=logging.INFO) # Set logging level for better feedback

    script_dir = os.path.dirname(__file__)
    output_test_dir = os.path.abspath(os.path.join(script_dir, '../output_test'))
    cleaned_md_path = os.path.join(output_test_dir, 'cleaned.md') 
    output_json_path = cleaned_md_path.replace('.md', '_sections.json')

    os.makedirs(output_test_dir, exist_ok=True)

    if not os.path.exists(cleaned_md_path):
        logging.warning(f"'{cleaned_md_path}' not found. Creating a dummy file for demonstration.")
        dummy_content = """
        <strong>TEST -- I</strong>
        <em><strong>Directions for questions 1 to 2:</strong></em>
        Read the following passages
        carefully and answer the questions that follow them.
        <strong>PASSAGE -- I</strong>
        Coal mining in Meghalaya and Assam, once a small-scale practice,
        expanded dangerously in the 1980s due to industrial demand from West
        Bengal and Bangladesh. The region's terrain made mechanised extraction
        difficult, leading to a proliferation of rat-hole mines. This hazardous
        method involves digging narrow tunnels that are barely large enough for
        a person to crawl through, posing significant risks to miners. Rat-hole
        mining occurs in two forms: side-cutting, which follows coal seams along
        hill slopes, and box-cutting, where miners dig pits up to 400 feet deep
        and extract coal horizontally, forming a tunnel network. This technique,
        prevalent in the north-east, particularly Meghalaya and the borders of
        Assam, poses significant safety and environmental hazards. The mining
        period stretches between November and March. Migrant labourers, often
        trapped in cycles of debt, are lured by 'Sardars' (labour agents) under
        exploitative conditions that amount to bonded labour. Reports highlight
        that children are trafficked into these mines due to their ability to
        navigate the narrow tunnels, making them easy targets for abuse. There
        are approximately 26,000 unclosed mine openings, each employing up to
        200 workers in shifts, putting thousands of labourers at daily risk in
        hazardous conditions.
        The National Green Tribunal (NGT) banned rat-hole mining on April 17,
        2014, due to environmental degradation and unsafe working conditions.
        This decision was later upheld by the Supreme Court in *State of
        Meghalaya v. All Dimasa Students Union* (2019). However, enforcement
        remains weak, as many illegal mines operate under the influence of
        powerful bureaucrats and coal mafias. Whistleblowers, including local
        officials and activists, face threats while authorities fail to hold
        perpetrators accountable.
        Several states indirectly enable rat-hole mining by exploiting
        regulatory loopholes. They are often under pressure from coal mafias and
        local politicians who profit from these illegal operations. For
        instance, the Meghalaya government has attempted to secure an exemption
        under Schedule 6, Paragraph 12A(b) of the Constitution to regulate coal
        mining on its own terms, bypassing national laws such as the Mines and
        Minerals (Development and Regulation) Act, 1957 (MMDR Act). The State
        Assembly even passed a resolution seeking this exemption, but the
        resolution remains unapproved. Economic and political interests drive
        this effort---coal mining generates revenue and employment---while
        powerful individuals with stakes in the industry resist enforcement of
        the ban. However, under Section 23C of the MMDR Act, Meghalaya is
        obligated to prevent illegal mining. Yet, it has failed to create
        state-level laws to enforce the 2014 NGT ban. As a result, illegal
        mining continues.
        \\<u>[Extracted, with edits and revisions, from \"[The Silent Crisis of
        Rat-Hole Mining]</u>\", by Utkarsh Yadav and Alokita, *The
        Hindu*\\]
        
        1. This is the first question text.
        (A) Option A
        (B) Option B
        (C) Option C
        (D) Option D

        2. This is the second question.
        It also has
        multiple lines.
        (A) Option A
        (B) Option B
        (C) Option C
        (D) Option D

        <strong>TEST -- II</strong>
        <em><strong>Directions for question 3:</strong></em>
        This is a
        single-line
        direction.

        3. This is the third question.
        (A) Option A
        (B) Option B
        """
        with open(cleaned_md_path, 'w', encoding='utf-8') as f:
            f.write(dummy_content)
        logging.info(f"Dummy '{cleaned_md_path}' created.")


    data = parse_cleaned_markdown(cleaned_md_path, None)

    def clean_text_for_json_values(text, is_main_common=False):
        if not isinstance(text, str):
            return text
        
        # Remove all question lines: <strong>n.</strong> or <strong>n. ...</strong>
        text = re.sub(r'<strong>\s*\d+\s*\.?[^<]*?</strong>.*?(?=(<strong>|$))', '', text, flags=re.DOTALL)
        # Remove all options: lines starting with (A)-(E) or [A-E] etc
        text = re.sub(r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*.*$', '', text, flags=re.MULTILINE)
        # Remove unnecessary backslashes (if not already handled)
        text = text.replace('\\', '')
        # Remove Markdown bold ** (if not already converted to <strong>)
        text = re.sub(r'\*\*', '', text)
        
        # --- NEW/UPDATED LOGIC FOR EXCLUDING PASSAGE LINES ---
        if is_main_common:
            # Pattern to match 'PASSAGE -- I' or 'PASSAGE I' possibly with strong tags, and remove the entire line.
            # This is more robust to variations and ensures the whole line is gone.
            passage_line_pattern = re.compile(
                r'^\s*(?:<strong>)?\s*PASSAGE\s*(?:[-–—]*\s*[IVX0-9]*\s*)?(?:</strong>)?\s*$', 
                re.IGNORECASE | re.MULTILINE
            )
            # Remove the entire line(s) that match the passage header pattern
            text = passage_line_pattern.sub('', text)
            
            # Also, remove any blank lines that might result immediately after removing a passage header,
            # but ensure normalize_and_strip_lines handles final consecutive newlines.
            text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE).strip() # Remove fully empty lines first if desired
        # --- END NEW/UPDATED LOGIC ---
        
        # Ensure normalization for these final fields (redundant with `normalize_and_strip_lines` in parse_cleaned_markdown
        # but ensures consistency if this `clean_text_for_json_values` is called independently or if upstream changes).
        return normalize_and_strip_lines(text)
            
    for section_name, section_data in data['Content'].items():
        questions = section_data['Data']['questions']

        for q in questions:
            if q['main_common_data']:
                cleaned_main = clean_text_for_json_values(q['main_common_data'], is_main_common=True)
                q['main_common_data'] = cleaned_main
            if q['sub_common_data']:
                cleaned_sub = clean_text_for_json_values(q['sub_common_data'])
                q['sub_common_data'] = cleaned_sub
            if q['Question']:
                cleaned_q = clean_text_for_json_values(q['Question'])
                q['Question'] = cleaned_q

        # Clean up any empty fields and ensure all questions have at least an empty string
        for q in questions:
            if not q['Question']:
                q['Question'] = ""
            if not q['sub_common_data']:
                q['sub_common_data'] = ""

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logging.info(f"Cleaned JSON saved to: {output_json_path}")

if __name__ == "__main__":
    import sys
    # Allow path to cleaned.md as a command-line argument
    if len(sys.argv) > 1:
        cleaned_md_path_arg = sys.argv[1]
        # Resolve to an absolute path
        abs_cleaned_md_path = os.path.abspath(cleaned_md_path_arg)
        # Ensure the directory exists
        os.makedirs(os.path.dirname(abs_cleaned_md_path), exist_ok=True)
        main_entry_path = abs_cleaned_md_path
    else:
        # Default path if no argument provided
        main_entry_path = 'modules/output_test/cleaned.md' # Adjust this default if needed

    # Re-route the main function to use the specified path for clarity
    def run_main_with_path(path):
        logging.basicConfig(level=logging.INFO) # Configure logging
        # Ensure output_test directory exists for default path
        output_test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../output_test'))
        os.makedirs(output_test_dir, exist_ok=True)

        data = parse_cleaned_markdown(path, None)

        # Final pass cleaning logic (copied from the original main())
        def clean_text_for_json_values_inner(text, is_main_common=False): # Renamed to avoid outer conflict
            if not isinstance(text, str):
                return text
            text = re.sub(r'<strong>\s*\d+\s*\.?[^<]*?</strong>.*?(?=(<strong>|$))', '', text, flags=re.DOTALL)
            text = re.sub(r'^[> \t]*[\(\[]([A-Ea-e1-5])[\)\]][)\. \t]*.*$', '', text, flags=re.MULTILINE)
            text = text.replace('\\', '')
            text = re.sub(r'\*\*', '', text)
            if is_main_common:
                # Updated regex for 'PASSAGE' removal
                passage_line_pattern = re.compile(
                    r'^\s*(?:<strong>)?\s*PASSAGE\s*(?:[-–—]*\s*[IVX0-9]*\s*)?(?:</strong>)?\s*$', 
                    re.IGNORECASE | re.MULTILINE
                )
                text = passage_line_pattern.sub('', text)
                text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE).strip() # Remove resulting blank lines
            return normalize_and_strip_lines(text) # Ensure final normalization

        for section_name, section_data in data['Content'].items():
            questions = section_data['Data']['questions']
            for q in questions:
                if q['main_common_data']:
                    q['main_common_data'] = clean_text_for_json_values_inner(q['main_common_data'], is_main_common=True)
                if q['sub_common_data']:
                    q['sub_common_data'] = clean_text_for_json_values_inner(q['sub_common_data'])
                if q['Question']:
                    q['Question'] = clean_text_for_json_values_inner(q['Question'])
            for q in questions:
                if not q['Question']:
                    q['Question'] = ""
                if not q['sub_common_data']:
                    q['sub_common_data'] = ""

        output_json_path_for_arg = path.replace('.md', '_sections.json')
        with open(output_json_path_for_arg, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Cleaned JSON saved to: {output_json_path_for_arg}")

    run_main_with_path(main_entry_path)