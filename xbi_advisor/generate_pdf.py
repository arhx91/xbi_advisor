"""Convert a markdown advisory report to a styled PDF using WeasyPrint."""

import logging
import os
import re
from pathlib import Path

import markdown
from PyPDF2 import PdfReader, PdfWriter
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

logger = logging.getLogger(__name__)


def generate_pdf(final_advice: str, output_path: Path) -> bool:
    """Generate a PDF from markdown content and save it to output_path."""
    logger.info("Starting PDF generation for: %s", output_path)

    # --- Step 1: Create a temporary markdown file ---
    tmp_dir = Path("/tmp") if Path("/tmp").is_dir() else Path("tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = tmp_dir / "temp_advice.md"

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(final_advice)

    # --- Step 2: Convert the temporary markdown file to PDF ---
    return _markdown_file_to_pdf(markdown_path, output_path)


def _preprocess_markdown_tables(markdown_content):
    """
    Find ```markdown code blocks and convert their content to HTML tables
    """
    pattern = r"```markdown\n([\s\S]*?)\n```"

    def replace_with_table(match):
        table_markdown = match.group(1)
        table_html = markdown.markdown(table_markdown, extensions=["tables"])
        return table_html

    processed_content = re.sub(pattern, replace_with_table, markdown_content)
    return processed_content


def _add_total_row_class(html_content):
    """
    Add 'total-row' class to table rows that start with 'Total'
    """
    # Pattern to find table rows where first cell contains "Total"
    # This regex looks for <tr> tags followed by <td> with "Total" at the start
    pattern = r"(<tr[^>]*>)\s*<td[^>]*>\s*(Total[^<]*)</td>"

    def add_class(match):
        tr_tag = match.group(1)
        # Check if class attribute already exists
        if "class=" in tr_tag:
            # Add to existing class
            tr_tag = tr_tag.replace('class="', 'class="total-row ')
            tr_tag = tr_tag.replace("class='", "class='total-row ")
        else:
            # Add new class attribute
            tr_tag = tr_tag.replace(">", ' class="total-row">')
        return f"{tr_tag}<td>{match.group(2)}</td>"

    return re.sub(pattern, add_class, html_content, flags=re.IGNORECASE)


def _add_page_structure(html_content: str) -> str:
    """
    Wrap the executive summary (everything before 'Detailed Analysis' h2) in a
    div with page-break-after so it occupies exactly the first page.
    """
    match = re.search(
        r"(<h2[^>]*>[^<]*Detailed Analysis[^<]*</h2>)", html_content, re.IGNORECASE
    )
    if match:
        exec_part = html_content[: match.start()]
        rest_part = html_content[match.start() :]
        return f'<div class="exec-summary-page">{exec_part}</div>{rest_part}'
    return html_content


def _markdown_file_to_pdf(markdown_path: Path, output_path: Path):
    """
    Convert a markdown file to a styled PDF using WeasyPrint.
    WeasyPrint properly handles Unicode characters like €, ', ", —, etc.

    Args:
        markdown_path: Path to markdown file
        output_path: Path to save the PDF file

    Returns:
        Boolean indicating if conversion was successful
    """
    if output_path is None:
        output_path = "xbi_advisor/final_recommendation/final_recommendation.pdf"

    logger.info("Reading markdown file: %s", markdown_path)

    try:
        with open(markdown_path, encoding="utf-8") as f:
            markdown_content = f.read()
    except OSError as e:
        logger.error("Error reading markdown file: %s", e)
        return False

    # Define brand colors
    VELVET = "#831B84"
    DARK_VELVET = "#561257"
    MAGENTA = "#E331D0"
    WHITE = "#FFFFFF"
    ALMOST_WHITE = "#faf8f8"
    BLACK = "#000000"

    # CSS - WeasyPrint has better CSS support than xhtml2pdf
    css = f"""
        @page {{
            size: A4;
            margin: 40px;
        }}

        introduction {{
            font-family: SuisseIntl-Regular, DejaVuSans, Arial, sans-serif;
            font-size: 18px;
            color: {VELVET};
            line-height: 1.4;
        }}

        body {{
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 11px;
            line-height: 1.5;
            color: {BLACK};
        }}

        h1 {{
            font-family: 'DejaVu Sans', Arial, sans-serif;
            color: {VELVET};
            font-size: 26px;
            border-bottom: 2px solid {VELVET};
            padding-bottom: 10px;
            font-weight: bold;
            margin-bottom: 20px;
        }}

        h2 {{
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 18px;
            color: {WHITE};
            background-color: {DARK_VELVET};
            padding: 8px 14px;
            margin-top: 30px;
            margin-bottom: 15px;
            font-weight: bold;
            line-height: 1.4;
            border-bottom: none;
            border-radius: 4px;
        }}

        h3 {{
            color: {DARK_VELVET};
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 16px;
            line-height: 1.4;
            margin-top: 20px;
            margin-bottom: 10px;
        }}

        h4 {{
            color: {DARK_VELVET};
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            margin-top: 15px;
            margin-bottom: 8px;
            font-weight: bold;
        }}

        a {{
            color: {MAGENTA};
            text-decoration: none;
        }}

        ul {{
            margin: 12px 0;
            padding-left: 20px;
            list-style-type: disc;
            display: list-item;
        }}

         /* Make bullet points visible */
        ul li {{
            list-style-type: disc;
            list-style-position: outside;
        }}

        ol {{
            margin: 12px 0;
            padding-left: 20px;
        }}

        li {{
            margin-bottom: 6px;
            padding-left: 5px;
            line-height: 1.5;
        }}

        ul li::marker {{
            color: {VELVET};
        }}

        table {{
            border-collapse: collapse;
            margin: 15px 0;
            width: 100%;
            max-width: 650px;
            font-size: 10px;
        }}

        th {{
            background-color: {VELVET};
            color: {WHITE};
            padding: 8px;
            text-align: left;
            font-weight: bold;
            font-size: 10px;
        }}

        th:first-child {{
            width: 55%;
        }}

        td {{
            padding: 8px;
            background-color: {ALMOST_WHITE};
            text-align: left;
            font-size: 10px;
            border-bottom: 1px solid #e0e0e0;
        }}

        td:not(:first-child) {{
            text-align: left;
        }}

        /* Total row styling */
        /* Style for total rows only */
        tr.total-row td {{
            font-weight: bold;
            background-color: #f0e6f0;
            border-bottom: none;
        }}

        p {{
            margin: 8px 0;
            line-height: 1.5;
        }}

        .document-header {{
            background-color: {DARK_VELVET};
            padding: 18px 20px;
            margin-bottom: 16px;
            border-radius: 5px;
            border-left: 6px solid {VELVET};
        }}

        .document-header h1 {{
            color: {WHITE};
            font-size: 22px;
            border-bottom: none;
            margin: 0;
            padding: 0;
        }}

        .document-footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid {VELVET};
            color: {BLACK};
            font-size: 10px;
            text-align: center;
            line-height: 1.2;
        }}

        /* Custom box classes */
        .info-box {{
            background-color: {ALMOST_WHITE};
            border: 2px solid {DARK_VELVET};
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}

        @media print {{
            body {{
                margin: 1cm;
                padding: 0;
            }}

            /* Ensuring table headers repeat on new pages */
            thead {{ display: table-header-group; }}
            tfoot {{ display: table-footer-group; }}
        }}

        /* === EXECUTIVE SUMMARY PAGE (page 1 only) === */
        .exec-summary-page {{
            page-break-after: always;
        }}

        .exec-summary-page h2 {{
            background-color: {DARK_VELVET};
            color: {WHITE};
            padding: 7px 14px;
            font-size: 15px;
            margin-top: 12px;
            margin-bottom: 7px;
            border-bottom: none;
            border-radius: 4px;
        }}

        .exec-summary-page h3 {{
            color: {VELVET};
            font-size: 12px;
            margin-top: 9px;
            margin-bottom: 4px;
            border-bottom: 1px solid {VELVET};
            padding-bottom: 2px;
        }}

        .exec-summary-page p {{
            margin: 3px 0;
            line-height: 1.4;
            font-size: 10.5px;
        }}

        .exec-summary-page table {{
            font-size: 9.5px;
            margin: 6px 0;
        }}

        .exec-summary-page th {{
            background-color: {VELVET};
            color: {WHITE};
            padding: 5px 8px;
            font-size: 9.5px;
        }}

        .exec-summary-page td {{
            padding: 4px 8px;
            background-color: #fdf5fe;
            font-size: 9.5px;
            border-bottom: 1px solid #ead5ea;
        }}

        .exec-summary-page tr.total-row td {{
            background-color: #f0d0f0;
            font-weight: bold;
            border-bottom: none;
        }}

        .exec-summary-page .info-box {{
            background-color: #fdf5fe;
            border: 1.5px solid {VELVET};
            padding: 7px 12px;
            border-radius: 4px;
            margin: 6px 0;
            font-size: 10px;
            line-height: 1.4;
        }}

    """

    # Preprocess markdown to handle ```markdown table blocks
    preprocessed_markdown = _preprocess_markdown_tables(markdown_content)

    # Convert markdown to HTML
    logger.info("Converting markdown to HTML...")
    html_content = markdown.markdown(
        preprocessed_markdown,
        extensions=[
            "tables",
            "fenced_code",
            "codehilite",
            "nl2br",
        ],
    )

    # Add 'total-row' class to rows starting with "Total"
    html_content = _add_total_row_class(html_content)

    # Wrap exec summary in page 1 div; Detailed Analysis starts on page 2
    html_content = _add_page_structure(html_content)

    # Create the complete HTML document with styling
    complete_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>XBI Advisor</title>
        <style>
            {css}
        </style>
    </head>
    <body>
        <div class="document-header">
            <h1>BI Advisory Report</h1>
        </div>
        <div class="content">
            {html_content}
        </div>
        <div class="document-footer">
            <p>Powered by Xebia's Analytics Engineering team</p>
        </div>
    </body>
    </html>
    """

    # Convert HTML to PDF using WeasyPrint
    logger.info("Converting HTML to PDF: %s", output_path)
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create PDF with WeasyPrint
        font_config = FontConfiguration()
        html_doc = HTML(string=complete_html)
        html_doc.write_pdf(str(output_path), font_config=font_config)

        logger.info("PDF successfully created at %s", output_path)
        return True

    except Exception as e:
        logger.error("Error creating PDF: %s", e)
        return False


def merge_pdfs(generated_pdf, front_page, final_pdf_path):
    """
    Merge the generated PDF with one additional PDF.

    Args:
        generated_pdf: Path to the newly generated PDF
        front_page: Path to the additional PDF to add
        final_pdf_path: Path for the final merged PDF

    Returns:
        Boolean indicating if merge was successful
    """
    try:
        pdf_writer = PdfWriter()

        # Add front page first
        with open(front_page, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                pdf_writer.add_page(page)

        # Add generated PDF
        if os.path.exists(generated_pdf):
            with open(generated_pdf, "rb") as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    pdf_writer.add_page(page)
            logger.info("Added %s", generated_pdf)
        else:
            logger.warning("Warning: %s not found, skipping", generated_pdf)

        # Write final PDF
        with open(final_pdf_path, "wb") as output_file:
            pdf_writer.write(output_file)

        logger.info("Successfully merged PDFs to %s", final_pdf_path)
        return True

    except Exception as e:
        logger.error("Error merging PDFs: %s", e)
        return False
