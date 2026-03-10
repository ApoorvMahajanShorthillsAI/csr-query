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
    
    # Detect column x-positions (simple heuristic)
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
        if not padded: return 0, 0
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

def process_sap_tables(pdf_path, output_base_dir):
    print(f"--- Starting extraction for: {pdf_path.name} ---")
    output_dir = output_base_dir / "SAP"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    table_map = {
        1: {"pages": [9], "title": "Summary of Changes"},
        2: {"pages": [10, 11], "title": "List of Primary and Secondary Objectives, Estimands, and Endpoints for Phase 1"},
        3: {"pages": [12, 13, 14, 15, 16, 17, 18], "title": "List of Primary, Secondary, and Tertiary/Exploratory Objectives, Estimands, and Endpoints for Phase 2/3"},
        4: {"pages": [27], "title": "Derived Variables for Presence of Each and Any Local Reaction Within 7 Days for Each Dose"},
        5: {"pages": [27], "title": "Local Reaction Grading Scale"},
        6: {"pages": [29], "title": "Systemic Event Grading Scale"},
        7: {"pages": [29], "title": "Scale for Fever"},
        8: {"pages": [33], "title": "Laboratory Abnormality Grading Scale"},
        9: {"pages": [45], "title": "Power Analysis for Noninferiority Assessment"},
        10: {"pages": [46], "title": "Probability of Observing at Least 1 AE by Assumed True Event Rates With Different Sample Sizes"},
        11: {"pages": [86], "title": "Interim Analysis Plan and Boundaries for Efficacy and Futility"},
        12: {"pages": [87], "title": "Statistical Design Operating Characteristics: Probability of Success or Failure for Interim Analyses"},
        13: {"pages": [87], "title": "Statistical Design Operating Characteristics: Probability of Success for Final Analysis and Overall"}
    }
    
    metadata = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for table_num, info in table_map.items():
            merged_rows = []
            header = None
            
            for page_num in info["pages"]:
                page_idx = page_num - 1
                if page_idx >= len(pdf.pages): continue
                page = pdf.pages[page_idx]
                
                # 1. Try standard extraction
                found_tables = page.extract_tables()
                
                # Identify which table on page matches the title
                target_table = None
                if len(found_tables) == 1:
                    target_table = found_tables[0]
                elif len(found_tables) > 1:
                    # Specific index handling for multi-table pages (27, 29, 87)
                    if page_num == 27:
                        target_table = found_tables[0] if table_num == 4 else found_tables[1]
                    elif page_num == 29:
                        target_table = found_tables[0] if table_num == 6 else found_tables[1]
                    elif page_num == 87:
                        target_table = found_tables[0] if table_num == 12 else found_tables[1]
                    else:
                        target_table = found_tables[0]
                
                # word-bounding-box fallback if needed (especially for Table 7 which might be borderless)
                if not target_table or (len(target_table) < 2 and table_num == 7):
                    df_w = extract_by_words(page)
                    if not df_w.empty:
                        target_table = [df_w.columns.tolist()] + df_w.values.tolist()
                
                if target_table:
                    clean_rows = clean_table_data(target_table)
                    if not clean_rows: continue
                    
                    if header is None:
                        header = clean_rows[0]
                        merged_rows.append(header)
                        merged_rows.extend(clean_rows[1:])
                    else:
                        # Check if first row is header repeating
                        if clean_rows[0] == header:
                            merged_rows.extend(clean_rows[1:])
                        else:
                            merged_rows.extend(clean_rows)
            
            if not merged_rows:
                print(f"Warning: Table {table_num} could not be extracted.")
                continue
                
            cols, rows = write_table_file(merged_rows, table_num, output_dir)
            
            metadata.append({
                "TableNumber": table_num,
                "Title": info["title"],
                "Pages": "-".join(map(str, info["pages"])),
                "Section": "Statistical Analysis Plan",
                "ColumnCount": cols,
                "RowCount": rows,
                "Description": f"Extraction of {info['title']}."
            })
            print(f"Captured Table {table_num} (Pages: {metadata[-1]['Pages']})")

    # Write metadata JSON
    with open(output_dir / "SAP_tables_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"--- Completed SAP extraction. ---")

if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\SAP.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_tables")
    process_sap_tables(p, b)
