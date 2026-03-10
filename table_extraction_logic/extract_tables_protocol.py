import pdfplumber
import pandas as pd
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# STEP 0 — Helpers
# ---------------------------------------------------------------------------

def clean_table_data(raw):
    """Replace None, newlines, and garbage-only cells. Skip blank rows."""
    if not raw:
        return []
    cleaned = []
    for row in raw:
        clean_row = []
        for cell in row:
            val = "" if cell is None else str(cell).replace("\n", " ").strip()
            # Remove garbage-only cells (dots, dashes, pipes, underscores, asterisks)
            if re.match(r'^[\.\-\s\|_\*]*$', val):
                val = ""
            clean_row.append(val)
        if any(c for c in clean_row):
            cleaned.append(clean_row)
    return cleaned


def is_repeated_header(row, canonical_header):
    """Return True if this row matches the canonical header."""
    if not canonical_header:
        return False
    clean = [str(c or "").strip() for c in row]
    # Check if a significant portion matches
    match_count = sum(1 for c, h in zip(clean, canonical_header) if c == h and c != "")
    return match_count >= len(canonical_header) // 2


def normalize_cols(rows):
    """Pad/trim rows to a consistent column count."""
    if not rows:
        return rows
    # Filter out None which might slip in
    valid_rows = [r for r in rows if r is not None]
    if not valid_rows:
        return []
    max_c = max(len(r) for r in valid_rows)
    return [(r + [""] * (max_c - len(r)))[:max_c] for r in valid_rows]


# ---------------------------------------------------------------------------
# EXTRACTION STRATEGIES
# ---------------------------------------------------------------------------

def extract_by_words(page):
    """Extract table from text-only pages using word bounding boxes."""
    words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
    if not words:
        return pd.DataFrame()
    
    # Filter out header/footer noise
    hf_keywords = ["ct05-gsop", "page:", "pfizer", "protocol no"]
    words = [w for w in words if not any(kw in w["text"].lower() for kw in hf_keywords)]
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
            if current_line:
                lines.append(current_line)
            current_line = [w]
            current_y = y
    if current_line:
        lines.append(current_line)
    
    if not lines:
        return pd.DataFrame()
    
    # Detect column x-positions
    all_xs = sorted(set(round(w["x0"] / 5) * 5 for line in lines for w in line))
    col_starts = [all_xs[0]]
    for x in all_xs[1:]:
        if x - col_starts[-1] > 25:
            col_starts.append(x)
    
    if len(col_starts) < 2:
        # Single-column narrative
        lines_text = [" ".join(w["text"] for w in sorted(l, key=lambda x: x["x0"])) for l in lines]
        return pd.DataFrame(lines_text, columns=["Content"])
    
    def assign_col(x0):
        dists = [abs(x0 - cs) for cs in col_starts]
        return dists.index(min(dists))
    
    table_rows = []
    for line in lines:
        row_cells = [""] * len(col_starts)
        for w in sorted(line, key=lambda x: x["x0"]):
            ci = assign_col(w["x0"])
            row_cells[ci] = (row_cells[ci] + " " + w["text"]).strip()
        if any(c for c in row_cells):
            table_rows.append(row_cells)
    
    if not table_rows:
        return pd.DataFrame()
    
    if len(table_rows) == 1:
        return pd.DataFrame(columns=table_rows[0])
    
    return pd.DataFrame(table_rows[1:], columns=table_rows[0])


def merge_section_pages(pdf, page_indices):
    """Merge tables across a section's pages, skipping repeated headers."""
    combined_rows = []
    canonical_header = None
    
    for pi in page_indices:
        if pi >= len(pdf.pages):
            continue
        page = pdf.pages[pi]
        tables = page.extract_tables()
        
        if not tables:
            # Fallback to word-based extraction
            df_fallback = extract_by_words(page)
            if not df_fallback.empty:
                # Use current header if found, else first row of fallback
                if canonical_header is None:
                    canonical_header = [str(c).strip() for c in df_fallback.columns]
                    combined_rows.append(canonical_header)
                combined_rows.extend(df_fallback.values.tolist())
            continue
        
        for t in tables:
            raw = clean_table_data(t)
            if not raw:
                continue
            if canonical_header is None:
                canonical_header = [str(c).strip() for c in raw[0]]
                combined_rows = list(raw)
            else:
                # Skip rows that exactly repeat the header
                data_rows = [r for r in raw if not is_repeated_header(r, canonical_header)]
                combined_rows.extend(data_rows)
    
    if not combined_rows:
        return pd.DataFrame()
    
    if len(combined_rows) == 1:
        return pd.DataFrame(columns=combined_rows[0])
    
    normalized = normalize_cols(combined_rows)
    # Ensure all rows have same length as header
    header = normalized[0]
    data = normalized[1:]
    return pd.DataFrame(data, columns=header)


# ---------------------------------------------------------------------------
# OUTPUT HELPERS
# ---------------------------------------------------------------------------

def write_table_file(output_dir, table_num, title, pages_str, section, df, description):
    """Write a single Table_N.md and return metadata dict."""
    filepath = output_dir / f"Table_{table_num}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Table {table_num}: {title}\n\n")
        if df.empty:
            f.write("> Content is redacted or not visible in source PDF.\n")
        else:
            f.write(df.to_markdown(index=False, tablefmt="github"))
            f.write("\n")
    row_count = 0 if df.empty else len(df)
    col_count = 0 if df.empty else len(df.columns)
    print(f"  \u2713 Table {table_num} ({title}): {row_count}r x {col_count}c")
    return {
        "TableNumber": table_num,
        "Title": title,
        "Pages": pages_str,
        "Section": section,
        "ColumnCount": col_count,
        "RowCount": row_count,
        "Description": description
    }


# ---------------------------------------------------------------------------
# MAIN PROCESSOR
# ---------------------------------------------------------------------------

def process_protocol_tables(pdf_path: Path, output_base_dir: Path):
    print(f'\n{"="*60}')
    print(f'PROTOCOL DEVIATION LOG TABLE EXTRACTION')
    print(f'{"="*60}')

    output_dir = output_base_dir / "Protocol"
    output_dir.mkdir(parents=True, exist_ok=True)

    for f in output_dir.glob("Table_*.md"):
        f.unlink()

    metadata_list = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  Total pages: {total_pages}")

        # --- Phase 1: TOC and Section Detection ---
        # Table 1: TOC (usually pages 1-3)
        t_num = 1
        title = "Table of Contents"
        toc_rows = []
        for pi in range(0, min(3, total_pages)):
            page = pdf.pages[pi]
            tbls = page.extract_tables()
            if tbls:
                for t in tbls:
                    toc_rows.extend(clean_table_data(t))
            else:
                df_w = extract_by_words(page)
                if not df_w.empty:
                    toc_rows.extend(df_w.values.tolist())
        
        df_toc = pd.DataFrame(toc_rows) if toc_rows else pd.DataFrame()
        metadata_list.append(write_table_file(
            output_dir, t_num, title, "1-3", "Document Overview",
            df_toc, "Index of protocol deviation categories and their page numbers."
        ))

        # Detect Section boundaries from headers
        section_boundaries = [] # list of (header_text, start_page_idx)
        keywords = [
            "eligibility", "informed consent", "dosing", "randomiz",
            "visit", "concomitant", "laboratory", "efficacy", "miscellaneous",
            "other", "protocol deviation", "inclusion", "exclusion"
        ]

        for i in range(3, total_pages):
            page = pdf.pages[i]
            text = (page.extract_text() or "").strip()
            # Look at first few lines for headers
            lines = text.split("\n")[:10]
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                if any(kw in line_clean.lower() for kw in keywords) and len(line_clean) < 100:
                    # Avoid duplicated headers from previous page or noise
                    if not section_boundaries or section_boundaries[-1][0] != line_clean:
                        section_boundaries.append((line_clean, i))
                        break

        # If no sections detected, treat all pages from 4 onwards as one big table
        if not section_boundaries:
            section_boundaries = [("Protocol Deviation Log", 3)]

        # --- Phase 2: Extract and Merge per Section ---
        for i, (name, start_pi) in enumerate(section_boundaries):
            t_num = i + 2
            end_pi = section_boundaries[i+1][1] - 1 if i+1 < len(section_boundaries) else total_pages - 1
            
            pages_str = f"{start_pi+1}-{end_pi+1}"
            df_section = merge_section_pages(pdf, range(start_pi, end_pi + 1))
            
            metadata_list.append(write_table_file(
                output_dir, t_num, name, pages_str, "Deviation Logs",
                df_section, f"Log entries for the protocol deviation category: {name}"
            ))

    # Save metadata
    metadata_path = output_dir / "Protocol_tables_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=4, ensure_ascii=False)
    
    print(f"\n  \u2713 Metadata saved to: {metadata_path.name}")
    print(f'{"="*60}\n')


if __name__ == '__main__':
    input_pdf_path = Path("Input documents for CSR/Protocol Devaition log.pdf")
    output_base = Path("artifacts/extracted_tables")
    process_protocol_tables(input_pdf_path, output_base)
