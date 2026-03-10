import pdfplumber
import pandas as pd
import json
import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

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

def extract_by_words(page):
    """Extract table from text using word bounding boxes (fallback for lineless tables)."""
    words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
    if not words:
        return pd.DataFrame()
    
    # Group into lines by y-position
    lines = []
    current_line = []
    current_y = None
    # Sort by Y, then X
    for w in sorted(words, key=lambda x: (round(x["top"] / 4) * 4, x["x0"])):
        y = round(w["top"] / 4) * 4
        if current_y is None or abs(y - current_y) <= 4:
            current_line.append(w)
            current_y = y
        else:
            if current_line: lines.append(current_line)
            current_line = [w]; current_y = y
    if current_line: lines.append(current_line)
    
    if not lines: return pd.DataFrame()
    
    # Detect column x-positions
    all_xs = sorted(set(round(w["x0"] / 5) * 5 for line in lines for w in line))
    col_starts = [all_xs[0]]
    for x in all_xs[1:]:
        if x - col_starts[-1] > 25: col_starts.append(x)
    
    def assign_col(x0):
        dists = [abs(x0 - cs) for cs in col_starts]
        return dists.index(min(dists))
    
    table_rows = []
    for line in lines:
        row_cells = [""] * len(col_starts)
        for w in sorted(line, key=lambda x: x["x0"]):
            ci = assign_col(w["x0"])
            row_cells[ci] = (row_cells[ci] + " " + w["text"]).strip()
        if any(c for c in row_cells): table_rows.append(row_cells)
    
    if not table_rows: return pd.DataFrame()
    if len(table_rows) == 1: return pd.DataFrame(columns=table_rows[0])
    return pd.DataFrame(table_rows[1:], columns=table_rows[0])

def write_table_file(table_data, table_num, output_dir):
    """Writes the table data to a markdown file."""
    if not table_data or (isinstance(table_data, list) and len(table_data) < 1):
        return 0, 0
    
    if isinstance(table_data, list):
        # Ensure column consistency
        max_cols = max(len(r) for r in table_data)
        padded = [(r + [""] * (max_cols - len(r))) for r in table_data]
        df = pd.DataFrame(padded[1:], columns=padded[0])
    else:
        df = table_data
        
    if df.empty: return 0, 0
    
    file_path = output_dir / f"Table_{table_num}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(df.to_markdown(index=False))
        
    return len(df.columns), len(df)

# ---------------------------------------------------------------------------
# MAIN PROCESSOR
# ---------------------------------------------------------------------------

def process_reports_tables(pdf_path, output_base_dir):
    print(f"--- Starting extraction for: {pdf_path.name} ---")
    output_dir = output_base_dir / "Reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    table_map = {
        1: {"page": 57, "title": "Overview of the Clinical Development Assessment report"},
        2: {"page": 58, "title": "Overview of the pivotal phase 3 study"},
        3: {"page": 77, "title": "Baseline Charlson Comorbidities"},
        4: {"page": 78, "title": "Efficacy Populations Vaccine Group"},
        5: {"page": 80, "title": "Vaccine Efficacy \u2013 subjects without evidence of infection"},
        6: {"page": 81, "title": "Vaccine Efficacy \u2013 subjects with or without evidence of infection"},
        7: {"page": 82, "title": "Vaccine Efficacy \u2013 after Dose 1"},
        8: {"page": 85, "title": "Vaccine Efficacy \u2013 by Subgroup (without evidence)"},
        9: {"page": 86, "title": "Vaccine Efficacy \u2013 by Subgroup (with or without evidence)"},
        10: {"page": 87, "title": "Vaccine Efficacy \u2013 by Requested Subgroup"},
        11: {"page": 88, "title": "Vaccine Efficacy \u2013 by Risk Status"},
        12: {"page": 90, "title": "First Severe COVID-19 Occurrence", "index": 0},
        13: {"page": 90, "title": "Summary of Efficacy for trial C4591001", "index": 1},
        14: {"page": 100, "title": "Safety Population, by Baseline SARS-CoV-2 Status"},
        15: {"page": 102, "title": "Systemic Events \u2013 Age Group 16-55 Years", "index": 0},
        16: {"page": 102, "title": "Systemic Events \u2013 Age Group >55 Years", "index": 1},
        17: {"page": 104, "title": "Adverse Event from Dose 1 to cutoff"},
        18: {"page": 105, "title": "Adverse Event from Dose 1 to 1 Month after Dose 2"},
        19: {"page": 106, "title": "Adverse Event From Dose 1 to 1 Month After Dose 2 - Safety Population"},
        20: {"page": 134, "title": "Effects Table for Comirnaty"}
    }
    
    metadata = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for table_num, info in table_map.items():
            page_idx = info["page"] - 1
            if page_idx >= len(pdf.pages): continue
            page = pdf.pages[page_idx]
            
            # 1. Try default extraction
            all_tables = page.extract_tables()
            
            # 2. Try word-based extraction if default fails or looks like garbage
            if not all_tables or len(all_tables[0]) < 2 or len(all_tables[0][0]) == 1:
                df_w = extract_by_words(page)
                if not df_w.empty:
                    # If multiple tables on page, this might need splitting, but for now we take the full thing
                    # or try to split if the user specified an index
                    rows_list = [df_w.columns.tolist()] + df_w.values.tolist()
                    all_tables = [rows_list]
            
            if not all_tables:
                print(f"Warning: No valid table found for Table {table_num} on page {info['page']}")
                continue
            
            target_idx = info.get("index", 0)
            if target_idx >= len(all_tables): target_idx = len(all_tables) - 1
            
            raw_table = all_tables[target_idx]
            clean_table = clean_table_data(raw_table)
            
            cols, rcount = write_table_file(clean_table, table_num, output_dir)
            
            if cols == 0: continue

            text = page.extract_text() or ""
            section = "Clinical Evaluation"
            metadata.append({
                "TableNumber": table_num,
                "Title": info["title"],
                "Pages": str(info["page"]),
                "Section": section,
                "ColumnCount": cols,
                "RowCount": rcount,
                "Description": f"Extraction of {info['title']}."
            })
            print(f"Captured Table {table_num} (Page {info['page']})")

    with open(output_dir / "Reports_tables_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
    print("--- Completed. ---")

if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\Reports (lab and tech).pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_tables")
    process_reports_tables(p, b)
