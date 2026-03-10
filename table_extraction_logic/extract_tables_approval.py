import re
import pdfplumber
import pandas as pd
import json
from pathlib import Path

def process_approval_tables(pdf_path: Path, output_base_dir: Path):
    """
    Specialized extraction for Approval_letter_Latest.pdf.
    Parses PMC schedules from text and formats as Markdown tables.
    """
    print(f"\n--- Extracting Structured Content from {pdf_path.name} ---")
    
    output_dir = output_base_dir / "Approval"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Remove page headers: "Page X – STN BL ... – Leslie Sands"
            text = re.sub(r'Page\s+\d+\s+–\s+STN\s+BL\s+.*?\n', '', text, flags=re.IGNORECASE)
            full_text += text + "\n"
            
    # Robust splitting instead of strict regex
    section_header = "POSTMARKETING COMMITMENTS SUBJECT TO REPORTING REQUIREMENTS"
    end_marker = "Please submit clinical protocols"
    
    if section_header in full_text:
        text_after_header = full_text.split(section_header)[1]
        
        section_text = text_after_header.split(end_marker)[0] if end_marker in text_after_header else text_after_header
        
        # Split by "1. ", "2. ", etc. at the start of a line or after a newline
        pmc_blocks = re.split(r'\n\s*(\d+)\.\s+', "\n" + section_text)
        
        # pmc_blocks[1] is "1", pmc_blocks[2] is text for PMC 1, etc.
        for i in range(1, len(pmc_blocks), 2):
            pmc_num = pmc_blocks[i]
            pmc_content = pmc_blocks[i+1] if i+1 < len(pmc_blocks) else ""
            
            # First part is the description, ends before the first Milestone (usually "Final Protocol Submission")
            desc_match = re.match(r'(.*?)(?=\n[A-Z][a-z]+)', pmc_content, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else pmc_content.strip()
            
            # Extract milestones and dates
            # Milestones: Final Protocol Submission, Study Initiation, Interim Results, Study Completion Date, Final Report Submission, Benefit/Risk Assessment Submission
            milestone_lines = re.findall(r'([A-Z][a-zA-Z/\s]+):\s+(.*)', pmc_content)
            
            for m_name, m_date in milestone_lines:
                all_data.append({
                    "PMC #": f"#{pmc_num}",
                    "Description": description,
                    "Milestone": m_name.strip(),
                    "Date": m_date.strip()
                })

    if all_data:
        df = pd.DataFrame(all_data)
        md_path = output_dir / "PMC_Schedules.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Postmarketing Commitment (PMC) Schedules\n\n")
            f.write(df.to_markdown(index=False, tablefmt="github"))
        print(f"  Saved {md_path.name}")
        
        # Generate Metadata
        metadata = [{
            "TableNumber": 1,
            "Title": "Postmarketing Commitment (PMC) Schedules",
            "Pages": "4-5",
            "Section": "POSTMARKETING COMMITMENTS SUBJECT TO REPORTING REQUIREMENTS",
            "ColumnCount": len(df.columns),
            "RowCount": len(df),
            "Description": "Extraction of PMC milestones and dates from the approval letter narrative."
        }]
        
        with open(output_dir / "Approval_tables_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        print(f"  Saved Approval_tables_metadata.json")
    else:
        print("  No PMC schedules detected.")

if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\Approval letter Latest.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_tables")
    process_approval_tables(p, b)
