import sys
import os
import re
import json
import logging
import markdown2
from pathlib import Path
from fpdf import FPDF
from fpdf.html import HTMLMixin
from query_agent import answer

# Setup logging
logging.basicConfig(level=logging.INFO, format="[report-gen] %(message)s")
logger = logging.getLogger(__name__)

QUERIES = [
    {
        "title": "Safety Findings",
        "query": "What were the most frequent local and systemic reactions for BNT162b2 in younger adults?",
    },
    {
        "title": "Study Methodology",
        "query": "Explain the study design and enrollment criteria for the BNT162 clinical trials.",
    },
    {
        "title": "Immunogenicity Results",
        "query": "Summarize the anti-S IgG response curves after vaccine administration as shown in the documents.",
    }
]

class CSRReport(FPDF, HTMLMixin):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "CSR Multimodal AI Agent: Clinical Query Report", ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def clean_text(text):
    """Sanitize and map Unicode characters for Latin-1 compatibility."""
    if not text:
        return ""
    # Map common clinical/formatting characters to Latin-1 or ASCII equivalents
    replacements = {
        "\u2022": "-",      # Bullet point
        "\u2219": "-",      # Small bullet
        "\u03bc": "u",      # Greek mu
        "\u2013": "-",      # en dash
        "\u2014": "--",     # em dash
        "\u2018": "'",      # Left single quote
        "\u2019": "'",      # Right single quote
        "\u201c": '"',      # Left double quote
        "\u201d": '"',      # Right double quote
        "\u00b1": "+/-",    # Plus-minus
        "\u2713": "v",      # Checkmark
        "\u2714": "v",      # Heavy checkmark
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Final pass to ensure Latin-1 compatibility
    return text.encode("latin-1", "replace").decode("latin-1").replace("?", " ")

def strip_md(text):
    """A robust regex-based stripper for Markdown artifacts."""
    if not text:
        return ""
    # Remove bold/italic markers
    text = re.sub(r'(\*\*|__)([\s\S]*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)([\s\S]*?)\1', r'\2', text)
    # Remove header markers
    text = re.sub(r'(?m)^#+\s*', '', text)
    text = re.sub(r'#+\s*', '', text)
    # Remove link markers
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Remove backticks and stray markers
    text = text.replace('`', '').replace('*', '').replace('#', '')
    # Remove list markers at start of lines
    text = re.sub(r'(?m)^[ \t]*[-*+]\s+', '', text)
    text = re.sub(r'(?m)^[ \t]*\d+\.\s+', '', text)
    return text.strip()

def render_figure(pdf, f):
    pdf.set_font("Helvetica", "B", 9)
    clean_fig_cap = strip_md(f['caption'])
    pdf.cell(0, 5, clean_text(f"- [{f['source_pdf']}] {clean_fig_cap} (Page {f['page_number']})"), ln=True)
    img_path = Path(f['file_path'])
    if img_path.exists():
        try:
            pdf.set_y(pdf.get_y() + 2)
            pdf.image(str(img_path), x=20, w=150)
            pdf.ln(2)
        except Exception as e:
            logger.warning(f"Failed to embed image {img_path}: {e}")
            
def render_table(pdf, t):
    pdf.set_font("Helvetica", "B", 10)
    clean_caption = strip_md(t['caption'])
    pdf.cell(0, 6, clean_text(f"> {clean_caption} (Source: {t['source_pdf']}, Page {t['page_number']})"), ln=True)
    try:
        md_path = Path(t['file_path'])
        if md_path.exists():
            md_content = md_path.read_text(encoding="utf-8")
            table_data = parse_markdown_table(md_content)
            if table_data:
                pdf.set_font("Helvetica", "", 8)
                with pdf.table(
                    borders_layout="ALL", 
                    cell_fill_color=(250, 250, 250), 
                    cell_fill_mode="ROWS",
                    line_height=5
                ) as table:
                    for row in table_data:
                        row_cells = table.row()
                        for cell in row:
                            row_cells.cell(strip_md(clean_text(cell)))
            pdf.ln(3)
    except Exception as e:
        logger.warning(f"Failed to render table {t.get('table_id', 'unknown')}: {e}")

def md_render(pdf, text, figures=None, tables=None, rendered_figs=None, rendered_tables=None):
    """Render markdown text as HTML if possible, or stripped text as fallback, avoiding repetition by chunking. Inlines figures/tables."""
    if not text:
        return
    
    if rendered_figs is None: rendered_figs = set()
    if rendered_tables is None: rendered_tables = set()
    
    text = clean_text(text)
    
    # Split by double newline to render paragraph-by-paragraph.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    for p in paragraphs:
        # If the paragraph has Markdown, try HTML rendering
        if any(c in p for c in ["*", "#", "_", "`", "[", "<"]):
            try:
                # Convert this specific paragraph to HTML
                html = markdown2.markdown(p)
                # FPDF2 supports a subset of HTML. Remove tags that often cause crashes.
                html = html.replace("<code>", "").replace("</code>", "")
                html = html.replace("<pre>", "").replace("</pre>", "")
                
                pdf.write_html(html)
                pdf.ln(2) # Add spacing between paragraphs
            except Exception as e:
                logger.warning(f"Paragraph rendering failed: {e}. Falling back to stripped version for this chunk.")
                pdf.multi_cell(0, 6, strip_md(p))
                pdf.ln(2)
        else:
            # Regular text paragraph
            pdf.multi_cell(0, 6, p)
            pdf.ln(2)
            
        # Check for inline figures
        if figures:
            for idx, f in enumerate(figures):
                if idx in rendered_figs: continue
                # Match "Figure X" or "Fig X" in caption
                match = re.search(r'(Figure\s+\d+|Fig\s+\d+|Figure\s+[A-Z0-9.-]+)', f['caption'], re.IGNORECASE)
                ref_name = match.group(1) if match else f['caption'][:15]
                if ref_name.lower() in p.lower():
                    pdf.ln(2)
                    render_figure(pdf, f)
                    rendered_figs.add(idx)
                    
        # Check for inline tables
        if tables:
            for idx, t in enumerate(tables):
                if idx in rendered_tables: continue
                match = re.search(r'(Table\s+(?:\d+|[A-Z0-9.-]+))', t['caption'], re.IGNORECASE)
                ref_name = match.group(1) if match else t['caption'][:15]
                if ref_name.lower() in p.lower():
                    pdf.ln(2)
                    render_table(pdf, t)
                    rendered_tables.add(idx)

def parse_markdown_table(md_content):
    """Simple parser for GFM tables into a list of lists."""
    lines = [line.strip() for line in md_content.split("\n") if line.strip()]
    rows = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            # Skip separator lines like |---|---|
            if all(c in "| -:" for c in line):
                continue
            cells = [cell.strip() for cell in line.split("|")][1:-1]
            rows.append(cells)
    return rows

def generate_pdf(results, output_path):
    pdf = CSRReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf.set_font("Helvetica", "", 11)
    md_render(pdf, "This report showcases the capabilities of the **CSR Multimodal AI Agent** in extracting, retrieving, and interpreting clinical study data (**Text**, **Tables**, and **Figures**) using Gemini 2.5 Pro.")
    pdf.ln(5)

    for i, res in enumerate(results):
        # Query Header
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 14)
        # Use strip_md for all labels
        clean_title = strip_md(res['title'])
        pdf.cell(0, 10, f"Query {i+1}: {clean_title}", ln=True, fill=True)
        pdf.ln(2)
        
        # Question
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Clinical Question:", ln=True)
        pdf.set_font("Helvetica", "", 11)
        md_render(pdf, res['query'])
        pdf.ln(2)

        # Answer
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "AI Analysis:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        rendered_figures = set()
        rendered_tables = set()
        
        md_render(pdf, res['answer'], figures=res.get('figures_used', []), tables=res.get('tables_used', []), rendered_figs=rendered_figures, rendered_tables=rendered_tables)
        pdf.ln(5)

        # Tables Used (Remaining)
        remaining_tables = [t for idx, t in enumerate(res.get('tables_used', [])) if idx not in rendered_tables]
        if remaining_tables:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, "Additional Tables Consulted:", ln=True)
            for t in remaining_tables:
                render_table(pdf, t)
            pdf.ln(2)

        # Figures Used (Remaining)
        remaining_figures = [f for idx, f in enumerate(res.get('figures_used', [])) if idx not in rendered_figures]
        if remaining_figures:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, "Additional Figures Consulted:", ln=True)
            for f in remaining_figures:
                render_figure(pdf, f)
            pdf.ln(5)

        # Sources
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, "Citations:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        source_str = ", ".join([f"{s['pdf']}.pdf (pg {s['page']})" for s in res['sources_cited']])
        # Stripping MD from sources too as it sometimes has ** markers
        pdf.multi_cell(0, 5, clean_text(strip_md(source_str)))
        
        if i < len(results) - 1:
            pdf.add_page()

    pdf.output(output_path)
    logger.info(f"Report generated: {output_path}")

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set.")
        return

    results = []
    base_dir = "."
    
    # Load assets once
    from ingestion import load_all_assets
    logger.info("Loading assets into memory...")
    assets = load_all_assets(base_dir)

    # Only keep the first query as requested by user
    for item in QUERIES[:1]:
        logger.info(f"Running query: {item['title']}...")
        try:
            res = answer(item['query'], base_dir=base_dir, assets=assets)
            res['title'] = item['title']
            results.append(res)
        except Exception as e:
            logger.error(f"Query failed: {e}")

    output_file = "CSR_Clinical_Query_Report.pdf"
    generate_pdf(results, output_file)
    print(f"SUCCESS: Created {output_file}")

if __name__ == "__main__":
    main()
