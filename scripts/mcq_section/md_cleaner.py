import re

def remove_markdown_tables(text):
    pattern = re.compile(
        r"""
        ^\s*-{5,}.*\n                         # Top horizontal rule (at least 5 dashes)
        (?:
            (?:^\s*\*\*[^\n]+\*\*\s+[^\n]+\n)+  # Lines with bolded label + spacing + values
            (?:^\s*\n)*                         # Optional blank lines between rows
        )+
        ^\s*-{5,}.*\n                         # Bottom horizontal rule
        """,
        re.MULTILINE | re.VERBOSE
    )
    return pattern.sub('', text)

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
    # --- Robust recursive LaTeX fraction handler using brace matching ---
    def parse_nested_latex_fraction(s):
        def find_brace_content(s, start):
            # Find content inside braces starting at s[start] == '{'
            assert s[start] == '{'
            depth = 0
            for i in range(start, len(s)):
                if s[i] == '{':
                    depth += 1
                elif s[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return s[start+1:i], i+1
            raise ValueError('Unmatched brace in LaTeX fraction')
        def helper(s):
            out = ''
            i = 0
            while i < len(s):
                if s[i:i+5] == '\\frac':
                    i += 5
                    while i < len(s) and s[i].isspace():
                        i += 1
                    if i < len(s) and s[i] == '{':
                        num, next_i = find_brace_content(s, i)
                        i = next_i
                        while i < len(s) and s[i].isspace():
                            i += 1
                        if i < len(s) and s[i] == '{':
                            den, next_i = find_brace_content(s, i)
                            i = next_i
                            num = helper(num)
                            den = helper(den)
                            # Parenthesize if needed
                            if any(op in num for op in ['+', '-', '×', '*', '/']):
                                if not (num.startswith('(') and num.endswith(')')):
                                    num = f'({num})'
                            if any(op in den for op in ['+', '-', '×', '*', '/']):
                                if not (den.startswith('(') and den.endswith(')')):
                                    den = f'({den})'
                            out += f'{num}/{den}'
                            continue
                if s[i] not in '{}':  # Exclude curly braces
                    out += s[i]
                i += 1
            return out
        return helper(s)

    # Apply to all $...$ and $$...$$ blocks
    def replace_all_latex_fractions(md):
        math_pattern = re.compile(r'(\${1,2})(.+?)(\1)', re.DOTALL)
        def math_repl(m):
            content = m.group(2)
            return parse_nested_latex_fraction(content)
        return math_pattern.sub(math_repl, md)
    # Also handle any stray \frac outside $...$
    md_content = parse_nested_latex_fraction(md_content)
    md_content = replace_all_latex_fractions(md_content)

    # Pre-processing step to identify and preserve complex LaTeX expressions
    # First, identify and process complex nested fractions - must happen before any other processing
    
    # Define a robust recursive nested fraction handler
    def parse_nested_latex_fraction(latex_expr):
        """
        Recursively parse and convert nested LaTeX fractions to readable text format
        with proper parentheses to maintain order of operations.
        
        This handles fractions of any nesting depth, including fractions inside
        both numerators and denominators, and preserves other mathematical operators.
        """
        # Handle basic LaTeX fraction pattern: \frac{numerator}{denominator}
        # This pattern matches \frac followed by optional whitespace, then the numerator and denominator in braces
        # It also handles cases with or without the backslash (plain frac)
        frac_pattern = re.compile(r'(?:\\)?frac\s*\{(.*?)\}\s*\{(.*?)\}')
        
        def process_match(match):
            # Extract numerator and denominator, handling balanced braces
            numerator_text = match.group(1).strip()
            denominator_text = match.group(2).strip()
            
            # Recursively process any nested fractions in numerator and denominator
            if 'frac' in numerator_text:
                numerator_text = parse_nested_latex_fraction(numerator_text)
            
            if 'frac' in denominator_text:
                denominator_text = parse_nested_latex_fraction(denominator_text)
            
            # Add parentheses if numerator or denominator contains operations
            # to maintain correct order of operations
            if any(op in numerator_text for op in ['+', '-', '×', '*', '/', ' ']):
                # Don't add extra parentheses if the numerator is already wrapped
                if not (numerator_text.startswith('(') and numerator_text.endswith(')')):
                    numerator_text = f"({numerator_text})"
                
            if any(op in denominator_text for op in ['+', '-', '×', '*', '/', ' ']):
                # Don't add extra parentheses if the denominator is already wrapped
                if not (denominator_text.startswith('(') and denominator_text.endswith(')')):
                    denominator_text = f"({denominator_text})"
                
            return f"{numerator_text}/{denominator_text}"
        
        # Keep processing until no more fractions found (handles multiple fractions at same level)
        prev_expr = None
        while latex_expr != prev_expr:
            prev_expr = latex_expr
            latex_expr = frac_pattern.sub(process_match, latex_expr)
            
            # Also handle edge cases without proper braces (like \frac 1 2 or frac 1 2)
            # These are less common but can occur in poorly formatted LaTeX
            edge_case_pattern = re.compile(r'(?:\\)?frac\s+(\S+)\s+(\S+)')
            latex_expr = edge_case_pattern.sub(lambda m: f"{m.group(1)}/{m.group(2)}", latex_expr)
        
        return latex_expr
    
    # Process all LaTeX expressions with nested fractions (both inside $ delimiters)
    def complex_nested_fraction_handler(match):
        # Extract the LaTeX expression (with or without $ delimiters)
        latex_expr = match.group(1) if match.group(1) else match.group(0)
        
        # Process the expression recursively
        result = parse_nested_latex_fraction(latex_expr)
        
        # Clean up any remaining LaTeX commands (including mathrm BEFORE removing braces)
        result = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', result)  # \mathrm{text}
        result = re.sub(r'\\mathrm([A-Za-z]+)', r'\1', result)  # \mathrm without braces
        result = re.sub(r'mathrm\{([^}]+)\}', r'\1', result)   # mathrm{text} without backslash
        result = re.sub(r'mathrm([A-Za-z]+)', r'\1', result)   # mathrm without backslash or braces
        # Handle mathrm directly beside symbols/text (no space/braces)
        result = re.sub(r'\\mathrm(?=[a-zA-Z])', '', result)    # \mathrm immediately before letters
        result = re.sub(r'mathrm(?=[a-zA-Z])', '', result)      # mathrm immediately before letters
        result = re.sub(r'\\mathrm(?=\W)', '', result)          # \mathrm before non-word characters
        result = re.sub(r'mathrm(?=\W)', '', result)            # mathrm before non-word characters
        result = re.sub(r'\\(?:left|right|text|rm|it|bf)(?:\{([^}]*)\}|([a-zA-Z]+))', r'\1\2', result)
        result = re.sub(r'\\([a-zA-Z]+)([ {}])', r'\1\2', result)
        
        # Return the result with appropriate delimiters if they were present
        if match.group(1):
            return f"${result}$"
        return result
    
    # Look for LaTeX expressions with nested fractions, both with and without $ delimiters
    # These patterns cover all combinations of nested fractions
    latex_frac_patterns = [
        re.compile(r'\$(.*?(?:\\|)frac\s*\{.*?\}\s*\{.*?(?:\\|)frac.*?\}.*?)\$'),  # Inside $ delimiters
        re.compile(r'(?:\\|)frac\s*\{.*?\}\s*\{.*?(?:\\|)frac.*?\}')               # Without delimiters
    ]
    
    for pattern in latex_frac_patterns:
        md_content = re.sub(pattern, complex_nested_fraction_handler, md_content)
    
    # Standard fraction handler for simpler cases
    def complex_fraction_handler(match):
        numerator = match.group(1).strip()
        denominator = match.group(2).strip()

        # Wrap if contains operations, but avoid double-wrapping
        if any(op in numerator for op in ['+', '-', '×', '*', '/']):
            if not (numerator.startswith('(') and numerator.endswith(')')):
                numerator = f"({numerator})"
                
        if any(op in denominator for op in ['+', '-', '×', '*', '/']):
            if not (denominator.startswith('(') and denominator.endswith(')')):
                denominator = f"({denominator})"

        return f"{numerator}/{denominator}"

    # Process any remaining simpler fractions
    def fix_nested_fractions(text):
        # Match both \frac and plain frac patterns
        frac_patterns = [
            re.compile(r'\\frac\s*\{(.*?)\}\s*\{(.*?)\}'),
            re.compile(r'(?<![a-zA-Z])frac\s*\{(.*?)\}\s*\{(.*?)\}')
        ]
        
        prev = None
        while text != prev:
            prev = text
            for pattern in frac_patterns:
                text = re.sub(pattern, lambda m: complex_fraction_handler(m), text)
        return text
    
    # Handle deeply nested fractions first
    md_content = fix_nested_fractions(md_content)
    
    # Process regular fractions
    md_content = re.sub(r'\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}', complex_fraction_handler, md_content)
    md_content = re.sub(r'frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}', complex_fraction_handler, md_content)
    
    # Fix common complex division expressions with ambiguous order of operations
    md_content = re.sub(r'(\d+)/([a-zA-Z])/(\d+)', r'(\2/\3)', md_content)
    md_content = re.sub(r'(\d+)\s*-\s*(\d+)/(\d+)', r'\1 - (\2/\3)', md_content)
    md_content = re.sub(r'([+\-])\s*(\d+)/(\d+)', r'\1 (\2/\3)', md_content)
    
    # Handle patterns like (d/45) + 360 - d/90 to (d/45) + ((360 - d)/90)
    md_content = re.sub(r'\(([a-zA-Z])/(\d+)\)\s*\+\s*(\d+)\s*-\s*\1/(\d+)', 
                      r'(\1/\2) + ((\3 - \1)/\4)', md_content)
    
    def replace_latex_symbols(md):
        # Replace common LaTeX math commands with Unicode
        # Only replace math symbols when preceded by a backslash or inside $...$
        # Remove all \mathrm{...} and \mathrm... variations (keep the content)
        md = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', md)  # \mathrm{text}
        md = re.sub(r'\\mathrm([A-Za-z]+)', r'\1', md)  # \mathrm without braces
        md = re.sub(r'mathrm\{([^}]+)\}', r'\1', md)   # mathrm{text} without backslash
        md = re.sub(r'mathrm([A-Za-z]+)', r'\1', md)   # mathrm without backslash or braces
        # Handle mathrm directly beside symbols/text (no space/braces)
        md = re.sub(r'\\mathrm(?=[a-zA-Z])', '', md)    # \mathrm immediately before letters
        md = re.sub(r'mathrm(?=[a-zA-Z])', '', md)      # mathrm immediately before letters
        md = re.sub(r'\\mathrm(?=\W)', '', md)          # \mathrm before non-word characters
        md = re.sub(r'mathrm(?=\W)', '', md)            # mathrm before non-word characters

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
            # First remove mathrm commands (BEFORE removing braces)
            expr = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', expr)  # \mathrm{text}
            expr = re.sub(r'\\mathrm([A-Za-z]+)', r'\1', expr)  # \mathrm without braces
            expr = re.sub(r'mathrm\{([^}]+)\}', r'\1', expr)   # mathrm{text} without backslash
            expr = re.sub(r'mathrm([A-Za-z]+)', r'\1', expr)   # mathrm without backslash or braces
            # Handle mathrm directly beside symbols/text (no space/braces)
            expr = re.sub(r'\\mathrm(?=[a-zA-Z])', '', expr)    # \mathrm immediately before letters
            expr = re.sub(r'mathrm(?=[a-zA-Z])', '', expr)      # mathrm immediately before letters
            expr = re.sub(r'\\mathrm(?=\W)', '', expr)          # \mathrm before non-word characters
            expr = re.sub(r'mathrm(?=\W)', '', expr)            # mathrm before non-word characters
            # Replace common LaTeX math commands with Unicode or plain text
            expr = re.sub(r'\\times', '×', expr)
            expr = re.sub(r'\\div', '÷', expr)
            expr = re.sub(r'\\cdot', '·', expr)
            expr = re.sub(r'\\pi', 'π', expr)
            expr = re.sub(r'\\degree', '°', expr)
            expr = re.sub(r'\\%', '%', expr)
            # Replace \frac{a}{b} inside math
            expr = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', lambda m: f"{m.group(1)}/{m.group(2)}", expr)
            # Remove unnecessary braces (AFTER mathrm removal)
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
    # Remove all inline image markdown (e.g., ![...](...))
    md_content = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', md_content)
    md_content = strip_image_attributes(md_content)
    # Remove all curly-brace image size attributes like {width="..." height="..."}, even with newlines/spaces
    md_content = re.sub(r'\{\s*width="[^"]*"\s*height="[^"]*"\s*\}', '', md_content, flags=re.DOTALL)
    md_content = re.sub(r'\{\s*height="[^"]*"\s*width="[^"]*"\s*\}', '', md_content, flags=re.DOTALL)
    md_content = re.sub(r'\{\s*width="[^"]*"\s*\}', '', md_content, flags=re.DOTALL)
    md_content = re.sub(r'\{\s*height="[^"]*"\s*\}', '', md_content, flags=re.DOTALL)
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
    
    # Final post-processing for LaTeX artifacts and media paths
    # Handle LaTeX spacing commands (mspace)
    md_content = re.sub(r'\\mspace\{[^}]*\}', ' ', md_content)
    md_content = re.sub(r'mspace\{[^}]*\}', ' ', md_content)
    md_content = re.sub(r'\\?mspace\d*mu', ' ', md_content)
    
    # Remove standalone 'frac' word and other LaTeX remnants
    md_content = re.sub(r'\bfrac\b', '', md_content)
    md_content = re.sub(r'\\text\{([^}]+)\}', r'\1', md_content)
    
    # Comprehensive mathrm removal - handle all variations
    md_content = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', md_content)  # \mathrm{text}
    md_content = re.sub(r'\\mathrm([A-Za-z]+)', r'\1', md_content)  # \mathrm without braces
    md_content = re.sub(r'mathrm\{([^}]+)\}', r'\1', md_content)   # mathrm{text} without backslash
    md_content = re.sub(r'mathrm([A-Za-z]+)', r'\1', md_content)   # mathrm without backslash or braces
    # Handle mathrm directly beside symbols/text (no space/braces)
    md_content = re.sub(r'\\mathrm(?=[a-zA-Z])', '', md_content)    # \mathrm immediately before letters
    md_content = re.sub(r'mathrm(?=[a-zA-Z])', '', md_content)      # mathrm immediately before letters
    md_content = re.sub(r'\\mathrm(?=\W)', '', md_content)          # \mathrm before non-word characters
    md_content = re.sub(r'mathrm(?=\W)', '', md_content)            # mathrm before non-word characters
    
    # Handle any remaining complex nested fractions or division expressions
    def nested_frac_handler(match):
        outer_num = match.group(1).strip()
        inner_expr = match.group(2).strip()
        
        # Try to identify inner fractions and wrap them in parentheses
        inner_expr = re.sub(r'([a-zA-Z0-9]+)/(\d+)', r'(\1/\2)', inner_expr)
        
        # If the inner expression has operators, wrap the whole thing
        if any(op in inner_expr for op in ['+', '-']):
            if not (inner_expr.startswith('(') and inner_expr.endswith(')')):
                inner_expr = f"({inner_expr})"
            
        return f"{outer_num}/{inner_expr}"
    
    # Find cases where a number is divided by an expression
    md_content = re.sub(r'(\d+)/([^/\s]+\s*[+\-]\s*[^/\s]+)', nested_frac_handler, md_content)
    
    # Fix common calculation errors in averages and means (match sum/n pattern)
    md_content = re.sub(r'(\s*=\s*)([\d\s×\+\-\*]+)(\s*=\s*)([\d\.]+)(\s*\.)', 
                     lambda m: f"{m.group(1)}({m.group(2)})/5{m.group(3)}{m.group(4)}{m.group(5)}", 
                     md_content)
    
    # Fix specific complex fraction cases (like question 49)
    md_content = re.sub(r'\$\\frac\{360\}\{\\frac\{d\}\{45\}\s*\+\s*\\frac\{360\s*-\s*d\}\{90\}\}\$', 
                     r'(360)/((d/45) + ((360-d)/90))', 
                     md_content)
    
    # Fix common typos in calculations
    md_content = re.sub(r'(\d+)\s*×\s*(\d+)5\b', r'\1 × \2', md_content)
    
    # Handle any single backslashes followed by text (e.g., \times, \div)
    md_content = re.sub(r'\\times', '×', md_content)
    md_content = re.sub(r'\\div', '÷', md_content)
    md_content = re.sub(r'\\cdot', '·', md_content)
    md_content = re.sub(r'\\pi', 'π', md_content)
    
    # Clean up media paths (remove duplicate media/media/)
    md_content = re.sub(r'media/media/', 'media/', md_content)
    
    # Clean up extra spaces
    md_content = re.sub(r'\s{2,}', ' ', md_content)
    
    # IMPORTANT: Remove mathrm BEFORE removing curly braces
    md_content = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', md_content)  # \mathrm{text}
    md_content = re.sub(r'\\mathrm([A-Za-z]+)', r'\1', md_content)  # \mathrm without braces
    md_content = re.sub(r'mathrm\{([^}]+)\}', r'\1', md_content)   # mathrm{text} without backslash
    md_content = re.sub(r'mathrm([A-Za-z]+)', r'\1', md_content)   # mathrm without backslash or braces
    # Handle mathrm directly beside symbols/text (no space/braces)
    md_content = re.sub(r'\\mathrm(?=[a-zA-Z])', '', md_content)    # \mathrm immediately before letters
    md_content = re.sub(r'mathrm(?=[a-zA-Z])', '', md_content)      # mathrm immediately before letters
    md_content = re.sub(r'\\mathrm(?=\W)', '', md_content)          # \mathrm before non-word characters
    md_content = re.sub(r'mathrm(?=\W)', '', md_content)            # mathrm before non-word characters
    
    # Remove all remaining curly braces as final cleanup (AFTER mathrm removal)
    md_content = re.sub(r'[{}]', '', md_content)
    
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
