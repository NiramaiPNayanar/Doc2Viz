import re

def remove_markdown_tables(text):
    pattern = re.compile(
        r'''
        ^\s*-{5,}.*\n           # Match top dashed line
        (?:.*\n)*?              # Match everything (non-greedy)
        ^\s*-{5,}.*\n           # Match bottom dashed line
        ''',
        re.MULTILINE | re.VERBOSE
    )
    return pattern.sub('', text)

def fix_linebreaks(text):
    lines = text.split('\n')
    fixed_lines = []
    buffer = ''
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                fixed_lines.append(buffer.strip())
                buffer = ''
            fixed_lines.append('')
        elif re.search(r'[.!?]["\')\]]*$', buffer.strip()):
            fixed_lines.append(buffer.strip())
            buffer = stripped
        else:
            buffer = (buffer + ' ' + stripped).strip()
    if buffer:
        fixed_lines.append(buffer.strip())
    return '\n'.join(fixed_lines)

import logging
from pylatexenc.latex2text import LatexNodes2Text

def strip_image_attributes(md_content):
    """Remove image size attributes from Markdown"""
    # Remove image size attributes from Markdown
    md_content = re.sub(r'(!\[[^\]]*\]\([^)]+\))\s*\{[^}]*\}', r'\1', md_content)
    md_content = re.sub(r'\{(width|height)="[^"]*"\}', '', md_content)
    # Clean up image paths: remove HTML tags, invisible unicode, whitespace, and normalize slashes
    def clean_md_image_path(match):
        alt = match.group(1)
        path = match.group(2)
        # Remove HTML tags
        path = re.sub(r'<[^>]+>', '', path)
        # Remove invisible unicode chars
        path = re.sub(r'[\u200c-\u206f]', '', path)
        # Remove whitespace and normalize slashes
        path = path.strip().replace('\\', '/').replace(' ', '')
        # If the path looks like a Windows absolute path, keep only the last media/image... segment if present
        m = re.search(r'(media/[^\s)]+)', path)
        if m:
            path = m.group(1)
        return f'![{alt}]({path})'
    md_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', clean_md_image_path, md_content)
    return md_content

def latex_to_readable(text):
    try:
        return LatexNodes2Text().latex_to_text(text)
    except Exception as e:
        logging.warning(f"Failed to convert LaTeX: {text}, Error: {e}")
        return text

def preprocess_latex_content(md_content):
    def latex_exclude_numbers(match):
        content = match.group(1)
        if re.match(r'^\(\d+\)$', content):
            return f'${content}$'
        return latex_to_readable(content)
    md_content = re.sub(r'(\*{1,3})\$\$([^$]+)\$\1', r'$$\2$$', md_content)
    md_content = re.sub(r'(\*{1,3})\$([^$]+)\$\1', r'$\2$', md_content)
    md_content = re.sub(r'\$\$(.*?)\$\$', lambda m: latex_exclude_numbers(m), md_content, flags=re.DOTALL)
    md_content = re.sub(r'\$(.*?)\$', lambda m: latex_exclude_numbers(m), md_content)
    md_content = re.sub(r'\\frac\{22\{7\}', r'\\frac{22}{7}', md_content)
    md_content = re.sub(r'\\text\{cm\}\^3', r'cm^3', md_content)
    return md_content

def convert_underline_syntax(md_content):
    md_content = re.sub(r'\*{1,2}\[([^\]]+)\]\{\.underline\}\*{1,2}', 
                        lambda m: f'<u>[{m.group(1)}]</u>', md_content)
    md_content = re.sub(r'\*{1,2}([\w\s\-\.,;:!\?\(\)\[\]"\']+)\{\.underline\}\*{1,2}', 
                        lambda m: f'<u>{m.group(1).strip()}</u>', md_content)
    md_content = re.sub(r'\[([^\]]+)\]\{\.underline\}', 
                        lambda m: f'<u>[{m.group(1)}]</u>', md_content)
    md_content = re.sub(r'([\w\s\-\.,;:!\?\(\)\[\]"\']+)\{\.underline\}', 
                        lambda m: f'<u>{m.group(1).strip()}</u>', md_content)
    md_content = re.sub(r'\*{1,2}\[([^\]]+)\]\{underline\}\*{1,2}', 
                        lambda m: f'<u>[{m.group(1)}]</u>', md_content)
    md_content = re.sub(r'\*{1,2}([\w\s\-\.,;:!\?\(\)\[\]"\']+)\{underline\}\*{1,2}', 
                        lambda m: f'<u>{m.group(1).strip()}</u>', md_content)
    md_content = re.sub(r'\[([^\]]+)\]\{underline\}', 
                        lambda m: f'<u>[{m.group(1)}]</u>', md_content)
    md_content = re.sub(r'([\w\s\-\.,;:!\?\(\)\[\]"\']+)\{underline\}', 
                        lambda m: f'<u>{m.group(1).strip()}</u>', md_content)
    return md_content

def clean_markdown_content(md_content, process_latex=True, process_underlines=True, save_json=False, cleaned_md_path=None):
    def replace_latex_symbols(md):
        # Replace common LaTeX math commands with Unicode
        # Only replace math symbols when preceded by a backslash or inside $...$
        # Remove all \mathrm{...} and \mathrm... (keep the content)
        md = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', md)
        md = re.sub(r'\\mathrm([A-Za-z]+)', r'\1', md)

        # Convert LaTeX fractions to plain text (\frac{a}{b} or frac{a}{b} or $\frac{a}{b}$)
        def frac_repl(m):
            num = m.group(1).strip()
            den = m.group(2).strip()
            return f'{num}/{den}'
        # Replace \frac{a}{b} and frac{a}{b} everywhere
        md = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', frac_repl, md)
        md = re.sub(r'(?<![a-zA-Z])frac\{([^{}]+)\}\{([^{}]+)\}', frac_repl, md)
        # Also handle $...$ math with \frac
        md = re.sub(r'\$\\frac\{([^{}]+)\}\{([^{}]+)\}\$', frac_repl, md)
        # Replace Profit\% with Profit% (inside math)
        md = re.sub(r'Profit\\%', 'Profit%', md)
        # Replace (1 + \frac{Profit%}{100}) or (1 + frac{Profit%}{100}) with (1 + Profit%/100)
        md = re.sub(r'\(1 \+ (?:\\frac|frac)\{Profit%\}\{100\}\)', r'(1 + Profit%/100)', md)
        # Also handle (1 + \frac{Profit\%}{100})
        md = re.sub(r'\(1 \+ (?:\\frac|frac)\{Profit\\%\}\{100\}\)', r'(1 + Profit%/100)', md)
        # Also handle $1 + \frac{Profit\%}{100}$
        md = re.sub(r'\$1 \+ (?:\\frac|frac)\{Profit\\%\}\{100\}\$', r'1 + Profit%/100', md)
        # Replace \% with %
        md = re.sub(r'\\%', '%', md)

        # Replace math expressions like $...$ with readable text (handle \times, \frac, etc.)
        def math_to_text(match):
            expr = match.group(1)
            # Replace common LaTeX math commands with Unicode or plain text
            expr = re.sub(r'\\times', '×', expr)
            expr = re.sub(r'\\div', '÷', expr)
            expr = re.sub(r'\\cdot', '·', expr)
            expr = re.sub(r'\\pi', 'π', expr)
            expr = re.sub(r'\\degree', '°', expr)
            expr = re.sub(r'\\%', '%', expr)
            # Replace \frac{a}{b} inside math
            expr = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', lambda m: f"{m.group(1)}/{m.group(2)}", expr)
            # Remove unnecessary braces
            expr = re.sub(r'[{}]', '', expr)
            # Remove \left, \right
            expr = re.sub(r'\\left|\\right', '', expr)
            # Remove any remaining backslashes
            expr = re.sub(r'\\', '', expr)
            return expr
        # Replace $...$ with readable text
        md = re.sub(r'\$([^$]+)\$', lambda m: math_to_text(m), md)
        # Replace $$...$$ with readable text
        md = re.sub(r'\$\$([^$]+)\$\$', lambda m: math_to_text(m), md)

        # Replace LaTeX commands (with backslash)
        replacements = [
            (r'\\cong', '≅'),
            (r'\\Delta', 'Δ'),
            (r'\\angle', '∠'),
            (r'\\sqrt', '√'),
            (r'\\leq', '≤'),
            (r'\\geq', '≥'),
            (r'\\neq', '≠'),
            (r'\\approx', '≈'),
            (r'\\times', '×'),
            (r'\\div', '÷'),
            (r'\\pm', '±'),
            (r'\\cdot', '·'),
            (r'\\infty', '∞'),
            (r'\\pi', 'π'),
            (r'\\degree', '°'),
            (r'\\ldots', '…'),
            (r'\\rightarrow', '→'),
            (r'\\leftarrow', '←'),
            (r'\\Rightarrow', '⇒'),
            (r'\\Leftarrow', '⇐'),
            (r'\\cup', '∪'),
            (r'\\cap', '∩'),
            (r'\\subset', '⊂'),
            (r'\\supset', '⊃'),
            (r'\\subseteq', '⊆'),
            (r'\\supseteq', '⊇'),
            (r'\\forall', '∀'),
            (r'\\exists', '∃'),
            (r'\\in', '∈'),
            (r'\\notin', '∉'),
            (r'\\to', '→'),
            (r'\\dots', '…'),
            (r'\\cdots', '⋯'),
            (r'\\overline', '‾'),
            (r'\\underline', '_'),
        ]
        for pat, rep in replacements:
            md = re.sub(pat, rep, md)

        # Do NOT replace plain 'angle' or 'Delta' in normal text (only in math context)
        return md

    def clean_option_blocks_and_formatting(md):
        # Split into lines for block processing
        lines = md.splitlines()
        cleaned_lines = []
        in_option_block = False
        option_regex = re.compile(r'^[ \t>]*\(([A-Ea-e1-5])\)(.*)$')
        # New: also match numeric options (1-9, 10, 11, ...)
        numeric_option_regex = re.compile(r'^[ \t>]*\((\d{1,3})\)(.*)$')
        for i, line in enumerate(lines):
            # Remove unnecessary leading '>' and whitespace from all lines
            line = re.sub(r'^[ \t>]+', '', line)
            m = option_regex.match(line)
            n = numeric_option_regex.match(line)
            if m:
                # Start of a new option block (A-E)
                in_option_block = True
                cleaned_lines.append(f'<strong>({m.group(1)})</strong>{m.group(2).rstrip()}')
                continue
            elif n:
                # Numeric option (always bold)
                cleaned_lines.append(f'<strong>({n.group(1)})</strong>{n.group(2).rstrip()}')
                continue
            if in_option_block:
                # If line is blank or a new question/section, end of option block
                if line.strip() == '' or re.match(r'^<strong>\d+\.', line) or re.match(r'^\([A-Ea-e1-5]\)', line):
                    in_option_block = False
                    cleaned_lines.append(line)
                    continue
                cleaned_lines.append(line.rstrip())
            else:
                # Add text formatting for bold, italics, underline, etc.
                formatted_line = line
                # Bold (**text** or __text__)
                formatted_line = re.sub(r'(?<![`$])\*\*([^*\n][^\n]*?[^*\n])\*\*(?![`$])', r'<strong>\1</strong>', formatted_line)
                formatted_line = re.sub(r'(?<![`$])__([^_\n][^\n]*?[^_\n])__(?![`$])', r'<strong>\1</strong>', formatted_line)
                # Italics (*text* or _text_)
                formatted_line = re.sub(r'(?<![`$])\*([^*\n][^\n]*?[^*\n])\*(?![`$])', r'<em>\1</em>', formatted_line)
                formatted_line = re.sub(r'(?<![`$])_([^_\n][^_\n]*?[^_\n])_(?![`$])', r'<em>\1</em>', formatted_line)
                # Underline (Markdown custom: [text]{.underline} or <u>text</u>)
                formatted_line = re.sub(r'\[([^\]]+)\]\{\.underline\}', r'<u>\1</u>', formatted_line)
                formatted_line = re.sub(r'<u>(.*?)</u>', r'<u>\1</u>', formatted_line)
                cleaned_lines.append(formatted_line.rstrip())
        return '\n'.join(cleaned_lines)
    md_content = clean_option_blocks_and_formatting(md_content)
    md_content = strip_image_attributes(md_content)
    md_content = replace_latex_symbols(md_content)
    # Fix for incomplete math expressions: e.g., (1 + Profit
    md_content = re.sub(r'\(1 \+ Profit\s*$', r'(1 + Profit%', md_content, flags=re.MULTILINE)
    # Remove any $...$ or $$...$$ left over (if any)
    md_content = re.sub(r'\$\$?([^$]+)\$\$?', lambda m: m.group(1), md_content)
    # Support for PASSAGE as a section header (like TEST)
    md_content = re.sub(r'^(\*{3}|\*{2})\s*PASSAGE\s*[-–]+\s*([A-Z0-9]+)\s*(\*{3}|\*{2})$', r'<strong>PASSAGE - \2</strong>', md_content, flags=re.MULTILINE|re.IGNORECASE)
    md_content = re.sub(r'^(\*{3})(\d{1,3}\.)\1', r'<strong><em>\2</em></strong>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^(\*{2})(\d{1,3}\.)\1', r'<strong>\2</strong>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^(\*{3})([A-Z][^*\n]+)\1', r'<strong><em>\2</em></strong>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^(\*{2})([A-Z][^*\n]+)\1', r'<strong>\2</strong>', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^\*\*\*\s*$', '---', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(?<![`$])\*\*\*([^*\n][^\n]*?[^*\n])\*\*\*(?![`$])', r'<strong><em>\1</em></strong>', md_content)
    md_content = re.sub(r'(?<![`$])\*\*([^*\n][^\n]*?[^*\n])\*\*(?![`$])', r'<strong>\1</strong>', md_content)
    md_content = re.sub(r'(?<![`$])\*([^*\n][^\n]*?[^*\n])\*(?![`$])', r'<em>\1</em>', md_content)
    md_content = re.sub(r'\{width=".*?" height=".*?"\}', '', md_content)
    md_content = re.sub(r'\\\s*\n', ' ', md_content)
    md_content = re.sub(r'\\([_()])', r'\1', md_content)
    md_content = re.sub(r'__<u>\[\((\d{1,3})\)\]</u>__', r'<u>[(\1)]</u>', md_content)
    def fill_in_blank(md):
        return re.sub(r'(?<!<u>)\b_{3,}\b(?!</u>)', '___', md)
    md_content = fill_in_blank(md_content)
    # Remove all tables (ASCII, Markdown, HTML, and ASCII-art course/ratio blocks)
    def remove_all_tables(md):
        # Remove Markdown tables using the new function
        md = remove_markdown_tables(md)
        # Remove ASCII boxed tables (robust, multiline, greedy)
        ascii_boxed_table_pattern = re.compile(
            r'(?:^\s*\+(?:[-=+:|*\s\w<>/]+)\+\s*\n'  # Top border
            r'(?:^\s*\|.*\n)+'                          # Table rows
            r'^\s*\+(?:[-=+:|*\s\w<>/]+)\+\s*\n?)',  # Bottom border
            re.MULTILINE
        )
        md = ascii_boxed_table_pattern.sub('', md)
        # Remove any block of consecutive lines that look like table rows (start and end with |)
        floating_table_rows_pattern = re.compile(r'(?:^\s*\|.*\|\s*\n)+', re.MULTILINE)
        md = floating_table_rows_pattern.sub('', md)
        # Remove any block of consecutive lines that look like ASCII/Markdown table borders (lines starting and ending with '+', '-', or '=')
        ascii_border_pattern = re.compile(r'(?:^\s*[+\-=_]{2,}.*[+\-=_]{2,}\s*\n)+', re.MULTILINE)
        md = ascii_border_pattern.sub('', md)
        # Remove HTML tables
        html_table_pattern = re.compile(r'<table[\s\S]*?</table>', re.IGNORECASE)
        md = html_table_pattern.sub('', md)
        # Strictly remove any block that visually resembles a table:
        # - Surrounded by lines of dashes/underscores/equals (5+)
        # - Or blocks of 2+ consecutive lines with multiple columns separated by 2+ spaces, colons, or pipes
        # - Or blocks of 2+ consecutive lines with repeated bold/italic/number/ratio patterns

        # Remove blocks surrounded by dashed/underscored/equal lines
        border_block_pattern = re.compile(
            r'(?:^\s*[-_=]{5,}.*\n)'  # top border
            r'(?:^.*\n)*?'            # content
            r'(?:^\s*[-_=]{5,}.*\n)', # bottom border
            re.MULTILINE
        )
        md = border_block_pattern.sub('', md)

        # Remove blocks of 2+ consecutive lines with 2+ columns (separated by 2+ spaces, colons, or pipes)
        multi_col_block_pattern = re.compile(
            r'(?:^(?:(?!\n)[^\n]*?([|:]|  +)[^\n]*)\n){2,}',
            re.MULTILINE
        )
        md = multi_col_block_pattern.sub('', md)

        # Remove ASCII-style ratio blocks with bold headers and values like "**BBA** 7 : 8"
        bold_ratio_block_pattern = re.compile(
            r'(?:^\s*[-=_]{5,}.*\n)?'                         # Optional top dashed border
            r'(?:^\s*(?:\*\*[^*\n]+\*\*\s+[^:]*:\s*\d+\s*)\n)+'  # Lines like "**BBA** 7 : 8"
            r'(?:^\s*\n)*'                                     # Optional blank lines
            r'(?:^\s*(?:\*\*[^*\n]+\*\*\s+[^:]*:\s*\d+\s*)\n)+'  # More lines like above
            r'(?:^\s*[-=_]{5,}.*\n)?',                         # Optional bottom dashed border
            re.MULTILINE
        )
        md = bold_ratio_block_pattern.sub('', md)

        # Remove any block of 2+ consecutive lines that look like table rows (start and end with |)
        floating_table_rows_pattern = re.compile(r'(?:^\s*\|.*\|\s*\n){2,}', re.MULTILINE)
        md = floating_table_rows_pattern.sub('', md)

        return md
    md_content = remove_all_tables(md_content)
    def superscript_and_subscript_replace(md):
        superscript_map = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','+':'⁺','-':'⁻','=':'⁼','(':'⁽',')':'⁾','n':'ⁿ','i':'ⁱ'}
        subscript_map = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉','+':'₊','-':'₋','=':'₌','(':'₍',')':'₎','n':'ₙ','a':'ₐ','e':'ₑ','o':'ₒ','x':'ₓ','i':'ᵢ','r':'ᵣ','u':'ᵤ','v':'ᵥ','s':'ₛ','t':'ₜ'}
        # Superscript: ^...^
        md = re.sub(r'\^([0-9n\+\-\=\(\)i]+)\^', lambda m: ''.join([superscript_map.get(c, c) for c in m.group(1)]), md)
        md = re.sub(r'(\d+)\^([a-zA-Z]{2,})\^', lambda m: f'{m.group(1)}{m.group(2)}', md)
        # Subscript: ~...~
        md = re.sub(r'~([0-9a-zA-Z\+\-\=\(\)]+)~', lambda m: ''.join([subscript_map.get(c, c) for c in m.group(1)]), md)
        # Special: (e.g. 2~n~ or ~2~Permutations)
        md = re.sub(r'~([0-9a-zA-Z\+\-\=\(\)]+)~([A-Za-z]+)', lambda m: ''.join([subscript_map.get(c, c) for c in m.group(1)]) + m.group(2), md)
        # Special: (e.g. Permutations~2~)
        md = re.sub(r'([A-Za-z]+)~([0-9a-zA-Z\+\-\=\(\)]+)~', lambda m: m.group(1) + ''.join([subscript_map.get(c, c) for c in m.group(2)]), md)
        # Frac text
        md = re.sub(r'(\d+)fractext([0-9]+)text([0-9]+)', lambda m: f'{m.group(1)} {m.group(2)}/{m.group(3)}', md)
        md = re.sub(r'fractext([0-9]+)text([0-9]+)', lambda m: f'{m.group(1)}/{m.group(2)}', md)
        unicode_fracs = {'1/2':'½','1/3':'⅓','2/3':'⅔','1/4':'¼','3/4':'¾','1/5':'⅕','2/5':'⅖','3/5':'⅗','4/5':'⅘','1/6':'⅙','5/6':'⅚','1/8':'⅛','3/8':'⅜','5/8':'⅝','7/8':'⅞'}
        for frac, uni in unicode_fracs.items():
            md = re.sub(rf'(^|\W){re.escape(frac)}(\W|$)', rf'\1{uni}\2', md)
        return md
    md_content = superscript_and_subscript_replace(md_content)
    md_content = re.sub(r'(?<!\\)\\(?![\\`*_{}\[\]()#+\-.!|])', '', md_content)
    if process_latex:
        md_content = preprocess_latex_content(md_content)
    if process_underlines:
        md_content = convert_underline_syntax(md_content)
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)
    md_content = re.sub(r'-{2,}', '-', md_content)
    md_content = fix_linebreaks(md_content)
    
    md_content = md_content.strip()

    # Optionally, create JSON after cleaning
    if save_json and cleaned_md_path:
        from md_to_json import parse_cleaned_markdown
        data = parse_cleaned_markdown(cleaned_md_path)
        json_path = cleaned_md_path.replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return md_content
