import pdfplumber
import pandas as pd
import json
import os
from pathlib import Path

def clean_table_data(table_data):
    """Replaces None with empty string and newlines with spaces."""
    if not table_data:
        return []
    cleaned = []
    for row in table_data:
        if row is None: continue
        cleaned_row = [str(cell).replace('\n', ' ').strip() if cell is not None else "" for cell in row]
        if any(cell != "" for cell in cleaned_row):
            cleaned.append(cleaned_row)
    return cleaned

def write_table_file(table_data, table_num, output_dir):
    """Writes the table data to a markdown file."""
    if not table_data or len(table_data) < 1:
        return 0, 0
    
    # Pad columns
    max_cols = max(len(r) for r in table_data)
    padded = [(r + [""] * (max_cols - len(r))) for r in table_data]
    
    if len(padded) == 1:
        df = pd.DataFrame(columns=padded[0])
    else:
        df = pd.DataFrame(padded[1:], columns=padded[0])
        
    file_path = output_dir / f"Table_{table_num}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(df.to_markdown(index=False))
        
    return len(df.columns), len(df)

def process_results_tables(pdf_path, output_base_dir):
    """Processes Table 1 in Results.pdf (Page 13)."""
    print(f"--- Starting extraction for: {pdf_path.name} ---")
    
    output_dir = output_base_dir / "Results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    metadata = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # Table 1 is on page 13 (index 12)
        page_idx = 12 
        if page_idx < len(pdf.pages):
            page = pdf.pages[page_idx]
            raw_table = page.extract_table()
            
            if not raw_table:
                print(f"Warning: No table found on page 13 of Results.pdf")
                return

            clean_table = clean_table_data(raw_table)
            cols, rows = write_table_file(clean_table, 1, output_dir)
            
            title = "Medical problems with onset from 7 days after Dose 2"
            metadata.append({
                "TableNumber": 1,
                "Title": title,
                "Pages": "13",
                "Section": "Medical Problems",
                "ColumnCount": cols,
                "RowCount": rows,
                "Description": "Table extracted from page 13 of Results.pdf as requested."
            })
            print(f"Extracted Table 1 from Page 13")

    # Write metadata JSON
    with open(output_dir / "Results_tables_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
    
    print(f"--- Extraction completed for {pdf_path.name}. ---")

if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\Results.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_tables")
    process_results_tables(p, b)
