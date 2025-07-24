import os
import re
import json

def parse_cleaned_markdown(cleaned_md_path, extracted_images=None):
    with open(cleaned_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all section headers (e.g., <strong>TEST -- I</strong> or <strong>Solutions</strong>)
    section_pattern = re.compile(r'<strong>\s*(TEST\s*[-–]+\s*[IVX1-9]+|Solutions)\s*</strong>', re.IGNORECASE)
    section_matches = list(section_pattern.finditer(content))
    sections = []
    if section_matches:
        for idx, match in enumerate(section_matches):
            section_name = match.group(1).strip() if match.group(1) else ''
            start = match.end()
            end = section_matches[idx+1].start() if idx+1 < len(section_matches) else len(content)
            section_content = content[start:end]
            sections.append((section_name, section_content))
    else:
        # No section headers, treat the whole file as one section with empty label
        sections = [('', content)]

    all_sections = {}
    for section_name, section_content in sections:
        section_label = section_name.replace('--', '-').strip() if section_name else ''
        # Remove the header line if present (for Solutions header)
        section_content = re.sub(r'<strong>\s*Solutions\s*</strong>\s*', '', section_content, flags=re.IGNORECASE)
        # Find all solution blocks robustly: <strong>n.</strong> ... Choice (x) (may have <strong> tags in choice)
        solution_split = re.split(r'(<strong>\d+\.</strong>)', section_content)
        solutions = []
        # Prepare visuals mapping if extracted_images/visuals are provided
        visuals_map = {}
        if extracted_images:
            for v in extracted_images:
                qnum = v.get('solution_number')
                if qnum is not None:
                    try:
                        qnum_int = int(qnum)
                    except Exception:
                        continue
                    if qnum_int not in visuals_map:
                        visuals_map[qnum_int] = {'Table': [], 'Image': []}
                    visuals_map[qnum_int]['Table'].extend(v.get('Table', []))
                    visuals_map[qnum_int]['Image'].extend(v.get('Image', []))
        for i in range(1, len(solution_split), 2):
            header = solution_split[i]
            body = solution_split[i+1] if (i+1) < len(solution_split) else ''
            # Extract solution number
            num_match = re.match(r'<strong>(\d+)\.</strong>', header)
            if not num_match:
                continue
            sol_num = int(num_match.group(1))
            # The body may contain <strong> tags, newlines, etc.
            # Extract the last occurrence of Choice (x) or Choice <strong>(x)</strong>
            choice_match = re.search(r'Choice\s*(?:<strong>)?\(?([0-9]+)\)?(?:</strong>)?', body, re.IGNORECASE)
            choice = int(choice_match.group(1)) if choice_match else None
            # Remove the choice line from the solution text
            sol_text = re.sub(r'Choice\s*(?:<strong>)?\(?[0-9]+\)?(?:</strong>)?', '', body, flags=re.IGNORECASE)
            # Remove only the matching phrase (e.g. 'Solutions for the questions 24 to 28:') but keep the rest of the text/lines, preserving line breaks
            sol_text = re.sub(r'<strong>\s*Solutions?\s+(for\s+)?(the\s+)?questions?\s+\d+\s*(to|-)?\s*\d+\s*:?', '', sol_text, flags=re.IGNORECASE)
            sol_text = re.sub(r'Solutions?\s+(for\s+)?(the\s+)?questions?\s+\d+\s*(to|-)?\s*\d+\s*:?', '', sol_text, flags=re.IGNORECASE)
            # Restore multiple consecutive spaces/newlines to a single space or newline, but preserve empty lines
            sol_text = re.sub(r' *\n', '\n', sol_text)
            sol_text = re.sub(r'\n{3,}', '\n\n', sol_text)
            # Remove any <strong> tags
            sol_text = re.sub(r'<[^>]+>', '', sol_text)
            # Trim leading/trailing whitespace from the whole block
            sol_text = sol_text.strip()
            # Attach Table/Image data if available, merging with any existing Table/Image in the solution body (if needed)
            table_data = visuals_map.get(sol_num, {}).get('Table', []) if visuals_map else []
            image_data = visuals_map.get(sol_num, {}).get('Image', []) if visuals_map else []
            # Log the table data for debugging
            # if table_data:
            #     print(f"[DEBUG] Solution {sol_num} Table Data: {table_data}")
            # If you want to merge with any Table/Image found in the body, add logic here
            solutions.append({
                'solution_number': sol_num,
                'Solution': sol_text,
                'Choice': choice,
                'Table': table_data,
                'Image': image_data
            })
        all_sections[section_label] = solutions

    return {
        'filename': os.path.basename(cleaned_md_path),
        **all_sections
    }
