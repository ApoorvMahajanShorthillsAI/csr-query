import os
import pandas as pd
import camelot
import pdfplumber
from pathlib import Path

def merge_logical_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Merge rows that are split across multiple lines in the PDF."""
    if df.empty: return df
    
    merged_rows = []
    current_row = None
    
    for _, row in df.iterrows():
        row_values = row.values.astype(str)
        if current_row is None:
            current_row = row_values
            continue
            
        # Refined Heuristic:
        # A row is a continuation if:
        # 1. Its first cell starts with a lowercase letter, or continuation markers like '(', 'above', 'in ages', 'participants', 'per 10,000'
        # 2. OR the first cell is empty AND there's content in other cells (common for wrapped text)
        first_cell = str(row.iloc[0]).strip()
        
        is_continuation = False
        if first_cell:
            lower_first = first_cell.lower()
            continuation_markers = ['(', 'above', 'in ages', 'participants', 'per 10,000', 'articles', 'interest', 'dec 2020', 'nov 2020']
            if any(lower_first.startswith(m) for m in continuation_markers):
                is_continuation = True
            elif first_cell[0].islower() and not first_cell.startswith('cid'): 
                is_continuation = True
        else:
            # First cell is empty - check if it's a wrapped data row or a standalone section header
            other_cells = [str(c).strip() for c in row[1:] if str(c).strip()]
            if len(other_cells) > 1:
                # Multiple columns have data - likely a wrapped data row
                is_continuation = True
            elif len(other_cells) == 1:
                # Only one column has data. If it's short, it might be a wrap. 
                # If it's long, it's likely a section header.
                content = other_cells[0]
                if len(content) < 20: 
                    is_continuation = True
                else:
                    is_continuation = False # Standalone section header
        
        if is_continuation:
            for col_idx in range(len(row)):
                cell_val = str(row.iloc[col_idx]).strip()
                if cell_val:
                    if current_row[col_idx] and current_row[col_idx] != 'nan':
                        current_row[col_idx] = f"{current_row[col_idx]} {cell_val}".strip()
                    else:
                        current_row[col_idx] = cell_val
        else:
            merged_rows.append(current_row)
            current_row = row_values
            
    if current_row is not None:
        merged_rows.append(current_row)
        
    return pd.DataFrame(merged_rows, columns=df.columns)

def clean_table_df(df: pd.DataFrame, table_id: str) -> pd.DataFrame:
    """Clean common artifacts and merge split rows."""
    if df.empty: return df

    # 1. Strip newlines early
    df = df.astype(str).replace(r'\n', ' ', regex=True)

    # 2. Merge logical rows (including potential multi-line headers if they aren't the very first row)
    df = merge_logical_rows(df)

    # 3. Handle noise at top
    for i in range(min(3, len(df))):
        row_str = " ".join(df.iloc[i].astype(str))
        if table_id.replace("_", " ") in row_str:
            df = df.iloc[i:]
            break
                
    # 4. If the first row contains the title, drop it
    if not df.empty and table_id.replace("_", " ") in " ".join(df.iloc[0].astype(str)):
        df = df.iloc[1:]
        
    # 5. Set header from first remaining row
    if not df.empty:
        new_header = df.iloc[0].astype(str)
        df = df[1:]
        df.columns = new_header

    # 6. Final cleanup of placeholder strings
    df = df.replace(r'^\s*$', pd.NA, regex=True).dropna(how='all').dropna(axis=1, how='all').fillna('')
    return df

def process_ae_tables(pdf_path: Path, output_base_dir: Path):
    """
    Specialized table extraction for AE.pdf (Fraiman et al.)
    Tables 1-4 using Camelot Stream + pdfplumber for footnotes.
    """
    print(f"\n--- Extracting Tables from {pdf_path.name} ---")
    
    ae_output_dir = output_base_dir / "AE"
    ae_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Extraction: Camelot (Stream mode verified as best for text-based tables here)
    try:
        # Table 1: pg 4, Table 2-3: pg 5, Table 4: pg 6
        tables = camelot.read_pdf(str(pdf_path), pages='4,5,6', flavor='stream')
        print(f"  Camelot found {len(tables)} table segments.")
    except Exception as e:
        print(f"  ❌ Camelot error: {e}")
        return

    # 2. Map segments to logical tables
    # Table 1: Found on page 4
    # Table 2: Found on page 5
    # Table 3: Found on page 5
    # Table 4: Found on page 6
    
    table_map = {
        "Table_1": [t for t in tables if t.page == 4 and "Table 1" in " ".join(t.df.iloc[:3].astype(str).values.flatten())],
        "Table_2": [t for t in tables if t.page == 5 and "Table 2" in " ".join(t.df.iloc[:3].astype(str).values.flatten())],
        "Table_3": [t for t in tables if t.page == 5 and "Table 3" in " ".join(t.df.iloc[:3].astype(str).values.flatten())],
        "Table_4": [t for t in tables if t.page == 6 and "Table 4" in " ".join(t.df.iloc[:3].astype(str).values.flatten())]
    }

    metadata_list = []

    with pdfplumber.open(pdf_path) as pdf:
        for table_id, segments in table_map.items():
            if not segments:
                print(f"  ⚠️ Could not find segment for {table_id}")
                continue
            
            # Combine segments if multiple (shouldn't happen here but for safety)
            df = pd.concat([s.df for s in segments])
            pg_num = segments[0].page
            
            df = clean_table_df(df, table_id)
            
            # Capture footnotes for this specific page
            page_text = pdf.pages[pg_num-1].extract_text()
            notes = []
            for line in page_text.split('\n'):
                if any(line.strip().startswith(prefix) for prefix in ["a ", "b ", "c ", "d ", "e ", "f "]):
                    notes.append(line.strip())
                elif "Note:" in line:
                    notes.append(line.strip())

            # Export Markdown
            md_path = ae_output_dir / f"{table_id}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# {table_id.replace('_', ' ')} (Page {pg_num})\n\n")
                f.write(df.to_markdown(index=False, tablefmt="github"))
                if notes:
                    f.write("\n\n### Notes/Footnotes\n")
                    for n in notes:
                        f.write(f"- {n}\n")
            
            # Prepare metadata
            table_num = int(table_id.split('_')[1])
            metadata_entry = {
                "TableNumber": table_num,
                "Title": table_id.replace('_', ' '),
                "Pages": str(pg_num),
                "Section": "Fraiman et al. Analysis",
                "ColumnCount": len(df.columns),
                "RowCount": len(df),
                "Description": f"Adverse events table {table_num} from Fraiman et al. publication."
            }
            metadata_list.append(metadata_entry)
            
            print(f"  ✅ Saved {md_path.name}")

    # Save metadata JSON
    import json
    metadata_path = ae_output_dir / "AE_tables_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=4)
        
    print(f"  ✅ Saved metadata to: {metadata_path.name}")

def main():
    # Individual test run
    input_dir = Path("Input documents for CSR")
    output_base_dir = Path("artifacts/extracted_tables")
    process_ae_tables(input_dir / "AE.pdf", output_base_dir)

if __name__ == "__main__":
    main()
