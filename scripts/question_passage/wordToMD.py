import os
import re
import subprocess
import logging
import sys

# Configure logging
logger = logging.getLogger(__name__)

class ConversionError(Exception):
    """Custom exception for conversion failures"""
    pass

def extract_docx_to_md(input_docx_path, output_md_path, extract_media=True, mathml=False):
    """Convert DOCX to Markdown with Pandoc with detailed error handling"""
    base_dir = os.path.dirname(os.path.abspath(output_md_path))
    media_dir = os.path.join(base_dir, 'media')
    if extract_media:
        os.makedirs(media_dir, exist_ok=True)
    logger.info(f"Converting DOCX to Markdown: {input_docx_path} -> {output_md_path}")
    cmd = ['pandoc', '-s', input_docx_path, '-o', output_md_path]
    if extract_media:
        cmd.append(f'--extract-media={media_dir}')
    if mathml:
        cmd.append('--mathml')
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Pandoc conversion successful")
        if result.stdout:
            logger.info(f"Pandoc output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Pandoc failed with code {e.returncode}: {e.stderr}")
        raise ConversionError(f"Pandoc conversion failed: {e.stderr}")
    except FileNotFoundError:
        error_msg = "Pandoc not found. Please install Pandoc and add to PATH."
        logger.error(error_msg)
        raise ConversionError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error during conversion: {str(e)}"
        logger.error(error_msg)
        raise ConversionError(error_msg)

def exclude_header(content):
    """Remove everything before the first TEST, Directions, or question number"""
    header_end = 0
    # Pattern for TEST section
    test_match = re.search(r'(^|\n)\s*(\*{0,3}\s*)?TEST', content, re.IGNORECASE)
    # Pattern for Directions
    directions_match = re.search(r'(^|\n)\s*(\*{0,3}\s*)?Directions', content, re.IGNORECASE)
    # Pattern for question number (handles **1.**, 1., Q.1, etc.)
    question_match = re.search(r'(^|\n)\s*(\*{0,3}\s*)?(Q\.?\s*)?\d{1,3}[\.)]', content)
    # Find the earliest match
    candidates = [(m.start(), m) for m in [test_match, directions_match, question_match] if m]
    if candidates:
        header_end, first_match = min(candidates, key=lambda x: x[0])
        if first_match == test_match:
            # Find the line number of TEST
            pre_content = content[:header_end]
            lines_before = pre_content.count('\n')
            all_lines = content.splitlines(True)  # keepends
            # Keep TEST line, but skip all lines until Directions or question number (after TEST)
            for i in range(lines_before+1, len(all_lines)):
                line = all_lines[i]
                if re.search(r'(Directions|(^\s*(\*{0,3}\s*)?(Q\.?\s*)?\d{1,3}[\.)]))', line, re.IGNORECASE):
                    content_wo_header = all_lines[lines_before] + ''.join(all_lines[i:]).lstrip()
                    break
            else:
                # If not found, just keep TEST line and the rest
                content_wo_header = all_lines[lines_before] + ''.join(all_lines[lines_before+1:]).lstrip()
        else:
            content_wo_header = content[header_end:].lstrip()
    else:
        content_wo_header = content.lstrip()
    return content_wo_header

def convert_docx_to_markdown(input_docx_path, output_base_dir, 
                           extract_media=True, mathml=False, 
                           save_md=True, extract_images=True):
    """
    DOCX to Markdown converter (conversion and header exclusion only)
    Args:
        input_docx_path: Path to input DOCX file
        output_base_dir: Base directory for output files
        extract_media: Whether to extract media files
        mathml: Whether to use MathML for equations
        save_md: Whether to save markdown file
        extract_images: Whether to extract images with detailed position info
    Returns:
        tuple: (md_content, md_path, media_dir, extracted_images)
    Raises:
        ConversionError: If conversion fails
    """
    os.makedirs(output_base_dir, exist_ok=True)
    md_path = os.path.join(output_base_dir, "content.md")
    media_dir = os.path.join(output_base_dir, 'media') if extract_media else None
    
    # Extract images and question mapping from HTML if requested
    extracted_images = []
    if extract_images:
        try:
            logger.info(f"Extracting images and question mapping from HTML for {input_docx_path}")
            images_dir = os.path.join(output_base_dir, 'html_extraction')
            from html_image_extractor import extract_images_via_html
            if not os.path.exists(input_docx_path):
                logger.warning(f"Document not found: {input_docx_path}")
            else:
                extracted_images = extract_images_via_html(input_docx_path, images_dir)
                logger.info(f"Extracted {len(extracted_images)} images (HTML-based) with question mapping")
                # Ensure all images have 'path' and propagate context_text if present
                for img in extracted_images:
                    if 'path' not in img and isinstance(img, str):
                        img['path'] = img
                extracted_images = [img for img in extracted_images if os.path.exists(img.get('path', ''))]
                if len(extracted_images) == 0:
                    logger.warning("No valid images were extracted or all image files are missing")
        except Exception as e:
            logger.warning(f"HTML image extraction failed: {e}")
            extracted_images = []
    
    extract_docx_to_md(input_docx_path, md_path, extract_media, mathml)
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise ConversionError(f"Failed to read converted markdown: {e}")
    content_wo_header = exclude_header(content)
    if save_md:
        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(content_wo_header)
            logger.info(f"Saved Markdown (header excluded): {md_path}")
        except Exception as e:
            logger.warning(f"Failed to save markdown: {e}")
    logger.info(f"Successfully converted DOCX to Markdown (header excluded)")
    return content_wo_header, md_path, media_dir, extracted_images

# Example usage for testing modular pipeline
if __name__ == "__main__":
    # Replace with your DOCX file path and output directory
    # test_docx = r"C:\Users\psuma\Downloads\MT2002501_Online.docx"  # Path to your test Word document
    # test_docx = r"C:\Users\psuma\Downloads\QWHO2502504.docx"  # Path to your test Word document
    # test_docx = r"D:\Projects_External\Intern\WordToPPT\test_files\QWHO2502504.docx"  # Path to your test Word document
    # test_docx = r"D:\Projects_External\Intern\WordToPPT\test_files\passage.docx"  # Path to your test Word document
    test_docx = sys.argv[1]
    
    test_output_dir = "output_test"
    try:
        md_content, md_path, media_dir, extracted_images = convert_docx_to_markdown(
            test_docx, test_output_dir,
            extract_media=True, mathml=True, save_md=True,
            extract_images=True
        )
        print(f"Conversion successful! Markdown (header excluded) saved at: {md_path}")
        # Remove tables from Markdown before cleaning
        from md_cleaner import clean_markdown_content, remove_markdown_tables
        md_content_no_tables = remove_markdown_tables(md_content)
        cleaned_md_path = os.path.join(test_output_dir, "cleaned.md")
        cleaned_content = clean_markdown_content(
            md_content_no_tables,
            save_json=False,  # Only clean, don't generate JSON here
            cleaned_md_path=cleaned_md_path
        )
        with open(cleaned_md_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        print(f"Cleaned markdown saved at: {cleaned_md_path}")

        # Now generate JSON from cleaned markdown with extracted images
        import json
        from md_to_json import parse_cleaned_markdown
        # Try to load visuals_from_extract_images.json if it exists
        visuals_json_path = os.path.join(os.path.dirname(cleaned_md_path), 'html_extraction', 'visuals_from_extract_images.json')
        visuals_data = None
        if os.path.exists(visuals_json_path):
            try:
                with open(visuals_json_path, 'r', encoding='utf-8') as vf:
                    visuals_data = json.load(vf)
                print(f"Loaded visuals from {visuals_json_path}")
            except Exception as e:
                print(f"Failed to load visuals JSON: {e}")
        # Pass visuals_data to md_to_json if available, else fallback to extracted_images
        data = parse_cleaned_markdown(cleaned_md_path, visuals_data if visuals_data is not None else extracted_images)
        json_path = cleaned_md_path.replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"JSON data saved at: {json_path}")

        # Now generate question images using json_to_question_images.py
        try:
            import subprocess
            script_path = os.path.join(os.path.dirname(__file__), 'json_to_question_images.py')
            # Pass --docxname as --filename (base name without extension)
            base_filename = os.path.splitext(os.path.basename(test_docx))[0] if 'test_docx' in locals() else 'docxfile'
            # Remove leading number and dash (e.g., 1752257752115-QWHO2502504 -> QWHO2502504)
            import re
            clean_base_filename = re.sub(r'^\d{8,}-', '', base_filename)
            subprocess.run([
                'python', script_path,
                '--json', json_path,
                '--docxname', base_filename
            ], check=True)
            print(f"Question images generated in: conversions/{clean_base_filename}")
        except Exception as e:
            print(f"Failed to generate question images: {e}")
    except Exception as e:
        print(f"Conversion or cleaning failed: {e}")

    # Delete output_test folder at the end if is_production is True
    is_production = True  # Set this as needed
    if is_production:
        import shutil
        if os.path.exists('output_test'):
            shutil.rmtree('output_test')