import pdfplumber
import pandas as pd
import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# STEP 0 — Helpers
# ---------------------------------------------------------------------------

def clean_cell(val):
    """Clean a single cell value."""
    if val is None:
        return ""
    val = str(val).replace("\n", " ").strip()
    # Remove garbage-only cells (dots, dashes, pipes)
    if re.match(r'^[\.\-\s\|_]*$', val):
        return ""
    return val


def clean_table_data(raw):
    """Replace None, newlines, and garbage-only cells. Skip blank rows."""
    if not raw:
        return []
    cleaned = []
    for row in raw:
        clean_row = [clean_cell(c) for c in row]
        if any(c for c in clean_row):
            cleaned.append(clean_row)
    return cleaned


def is_header_footer_row(row):
    """Skip repeating page header/footer rows (doc number, page counter)."""
    row_str = " ".join(str(c) for c in row).lower()
    skip_patterns = [
        "ct05-gsop", "page:", "of 35", "of35",
        "pfizer confidential", "protocol number"
    ]
    return any(p in row_str for p in skip_patterns)


def clean_and_filter(raw):
    """Clean table data and remove header/footer rows."""
    cleaned = clean_table_data(raw)
    return [r for r in cleaned if not is_header_footer_row(r)]


def normalize_cols(rows, expected_cols=None):
    """Pad/trim rows to a consistent column count."""
    if not rows:
        return rows
    max_c = expected_cols or max(len(r) for r in rows)
    result = []
    for r in rows:
        padded = (r + [""] * (max_c - len(r)))[:max_c]
        result.append(padded)
    return result


def rows_to_df(rows):
    """Convert row list (first row = header) to DataFrame."""
    if not rows or len(rows) < 2:
        return pd.DataFrame()
    normalized = normalize_cols(rows)
    return pd.DataFrame(normalized[1:], columns=normalized[0])


def words_to_df(page):
    """
    Use pdfplumber word bboxes to reconstruct columnar text-based tables.
    Groups words into rows by y-position tolerance, then into columns by x-clusters.
    Returns a DataFrame or empty DataFrame if content looks non-tabular.
    """
    words = page.extract_words(x_tolerance=3, y_tolerance=3) or []
    if not words:
        return pd.DataFrame()

    # Filter out header/footer text
    hf_keywords = ["ct05-gsop", "page:", "pfizer", "protocol no"]
    words = [w for w in words if not any(kw in w["text"].lower() for kw in hf_keywords)]
    if not words:
        return pd.DataFrame()

    # Group words into lines by y-tolerance of 5
    lines = []
    current_line = []
    current_y = None
    for w in sorted(words, key=lambda x: (round(x["top"] / 5) * 5, x["x0"])):
        y = round(w["top"] / 5) * 5
        if current_y is None or abs(y - current_y) <= 5:
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

    # Build X-coordinate clusters to detect columns
    all_xs = [w["x0"] for line in lines for w in line]
    all_xs.sort()

    # Simple column detection: cluster x-positions with gap > 30
    col_starts = [all_xs[0]]
    for x in all_xs[1:]:
        if x - col_starts[-1] > 30:
            col_starts.append(x)

    # If only 1 column cluster found, treat as single-column narrative
    if len(col_starts) < 2:
        text_lines = []
        for line in lines:
            txt = " ".join(w["text"] for w in sorted(line, key=lambda x: x["x0"]))
            txt = txt.strip()
            if txt:
                text_lines.append(txt)
        if not text_lines:
            return pd.DataFrame()
        return pd.DataFrame(text_lines, columns=["Content"])

    # Assign each word to closest column bucket
    def assign_col(x0):
        dists = [abs(x0 - cs) for cs in col_starts]
        return dists.index(min(dists))

    # Build table rows
    table_rows = []
    for line in lines:
        row_cells = [""] * len(col_starts)
        for w in sorted(line, key=lambda x: x["x0"]):
            ci = assign_col(w["x0"])
            sep = " " if row_cells[ci] else ""
            row_cells[ci] += sep + w["text"]
        # Clean cells
        row_cells = [c.strip() for c in row_cells]
        if any(c for c in row_cells):
            table_rows.append(row_cells)

    if not table_rows:
        return pd.DataFrame()
    if len(table_rows) == 1:
        # Single row — treat as header with no data
        return pd.DataFrame(columns=table_rows[0])

    return pd.DataFrame(table_rows[1:], columns=table_rows[0])


def merge_grid_pages(pdf, page_indices, table_idx=0):
    """Merge grid tables spanning multiple pages, deduplicating headers."""
    combined_rows = []
    canonical_header = None
    for pi in page_indices:
        if pi >= len(pdf.pages):
            continue
        tables = pdf.pages[pi].extract_tables()
        if not tables or table_idx >= len(tables):
            continue
        raw = clean_and_filter(tables[table_idx])
        if not raw:
            continue
        if canonical_header is None:
            canonical_header = raw[0]
            combined_rows = list(raw)
        else:
            if raw[0] == canonical_header:
                combined_rows.extend(raw[1:])
            else:
                combined_rows.extend(raw)
    return combined_rows


def merge_word_pages(pdf, page_indices):
    """Merge word-extracted tables from multiple pages."""
    frames = []
    for pi in page_indices:
        if pi >= len(pdf.pages):
            continue
        df = words_to_df(pdf.pages[pi])
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]
    # Concat with outer join to handle different column sets
    try:
        return pd.concat(frames, ignore_index=True, sort=False).fillna("")
    except Exception:
        # Last resort: just return the first usable frame
        return frames[0]


def write_table_file(output_dir, table_num, title, pages_str, section, df, description):
    """Write a single Table_N.md (no inline metadata) and return metadata dict."""
    filepath = output_dir / f"Table_{table_num}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Table {table_num}: {title}\n\n")
        if df.empty:
            f.write("> Content not visible or non-tabular in source PDF.\n")
        else:
            f.write(df.to_markdown(index=False, tablefmt="github"))
            f.write("\n")
    row_count = 0 if df.empty else len(df)
    col_count = 0 if df.empty else len(df.columns)
    print(f"  \u2713 Table {table_num} ({title}): {row_count} rows x {col_count} cols")
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
# Main extraction function
# ---------------------------------------------------------------------------

def process_icfs_tables(pdf_path: Path, output_base_dir: Path):
    print(f'\n{"="*60}')
    print(f'ICFs.pdf TABLE EXTRACTION')
    print(f'{"="*60}')

    output_dir = output_base_dir / "ICFs"
    output_dir.mkdir(parents=True, exist_ok=True)

    for f in output_dir.glob("Table_*.md"):
        f.unlink()

    metadata_list = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  Total pages: {total_pages}")

        # -------------------------------------------------------------------
        # Table 1 — Page 1 (index 0) — Grid
        # Document Header Block (Study, Country, Site, Protocol)
        # -------------------------------------------------------------------
        t_num = 1
        title = "Participant Information and Consent Form — Document Header"
        pages_str = "1"
        page = pdf.pages[0]
        grid_tables = page.extract_tables()
        if grid_tables:
            raw = clean_and_filter(grid_tables[0])
            df = rows_to_df(raw) if (raw and len(raw) >= 2) else words_to_df(page)
        else:
            df = words_to_df(page)
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Document Header", df,
            "Header identification block — Study, Country, Site, Protocol, Sponsor, ICD version."
        ))

        # -------------------------------------------------------------------
        # Table 2 — Page 1 additional grid table
        # Consent Form Version tracking
        # -------------------------------------------------------------------
        t_num = 2
        title = "Consent Form — Version and Amendment Tracking"
        pages_str = "1"
        page = pdf.pages[0]
        grid_tables = page.extract_tables()
        if grid_tables and len(grid_tables) > 1:
            raw = clean_and_filter(grid_tables[1])
            df = rows_to_df(raw) if (raw and len(raw) >= 2) else pd.DataFrame()
        else:
            # Extract all text from page to find version info
            df = words_to_df(page)
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Document Header", df,
            "Version tracking table for the ICF document — includes amendment dates and version numbers."
        ))

        # -------------------------------------------------------------------
        # Table 3 — Pages 7–8 (indices 6–7)
        # Visit Schedule — Screening and Baseline
        # -------------------------------------------------------------------
        t_num = 3
        title = "Visit Schedule — Screening and Baseline"
        pages_str = "7-8"
        rows = merge_grid_pages(pdf, [6, 7], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [6, 7])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Study Visit Schedule", df,
            "Visit schedule for the screening and baseline periods of the BNT162b2 clinical trial."
        ))

        # -------------------------------------------------------------------
        # Table 4 — Pages 8–10 (indices 7–9)
        # Visit Schedule — Doses and Follow-up
        # -------------------------------------------------------------------
        t_num = 4
        title = "Visit Schedule — Vaccination Doses and Follow-up"
        pages_str = "8-10"
        rows = merge_grid_pages(pdf, [7, 8, 9], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [7, 8, 9])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Study Visit Schedule", df,
            "Visit schedule for dose 1, dose 2, and follow-up visits."
        ))

        # -------------------------------------------------------------------
        # Table 5 — Pages 10–12 (indices 9–11)
        # Schedule of Activities (SOA) — Primary
        # This is a proper grid table successfully extracted by pdfplumber
        # -------------------------------------------------------------------
        t_num = 5
        title = "Schedule of Activities (SOA) — Primary"
        pages_str = "10-12"
        rows = merge_grid_pages(pdf, [9, 10, 11], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [9, 10, 11])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Schedule of Activities", df,
            "Primary schedule of study activities, procedures, and assessments by visit."
        ))

        # -------------------------------------------------------------------
        # Table 6 — Pages 12–13 (indices 11–12)
        # Schedule of Activities (SOA) — Continued
        # -------------------------------------------------------------------
        t_num = 6
        title = "Schedule of Activities (SOA) — Continued"
        pages_str = "12-13"
        rows = merge_grid_pages(pdf, [11, 12], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [11, 12])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Schedule of Activities", df,
            "Continuation of the schedule of activities covering post-delivery follow-up."
        ))

        # -------------------------------------------------------------------
        # Table 7 — Pages 13–14 (indices 12–13)
        # Participant Rights / Risk-Benefit Summary
        # -------------------------------------------------------------------
        t_num = 7
        title = "Participant Rights and Risk-Benefit Summary"
        pages_str = "13-14"
        rows = merge_grid_pages(pdf, [12, 13], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [12, 13])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Rights and Benefits", df,
            "Summary of participant rights, risks, and potential benefits of study participation."
        ))

        # -------------------------------------------------------------------
        # Table 8 — Pages 14–15 (indices 13–14)
        # Emergency and Study Contact Information
        # -------------------------------------------------------------------
        t_num = 8
        title = "Emergency and Study Contact Information"
        pages_str = "14-15"
        rows = merge_grid_pages(pdf, [13, 14], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [13, 14])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Contact Information", df,
            "Study investigator, site coordinator, and emergency telephone contact details."
        ))

        # -------------------------------------------------------------------
        # Table 9 — Pages 15–17 (indices 14–16)
        # COVID-19 Infection Risk Summary
        # -------------------------------------------------------------------
        t_num = 9
        title = "COVID-19 Infection Risk Summary"
        pages_str = "15-17"
        rows = merge_grid_pages(pdf, [14, 15, 16], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [14, 15, 16])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Risk Information", df,
            "Summary of COVID-19 infection risks for relevant population groups."
        ))

        # -------------------------------------------------------------------
        # Table 10 — Pages 17–20 (indices 16–19)
        # Vaccine Side Effects Frequency Table
        # -------------------------------------------------------------------
        t_num = 10
        title = "Vaccine Side Effects and Frequency Table"
        pages_str = "17-20"
        rows = merge_grid_pages(pdf, [16, 17, 18, 19], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [16, 17, 18, 19])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Side Effects", df,
            "Frequency and severity of solicited and unsolicited adverse events post-vaccination."
        ))

        # -------------------------------------------------------------------
        # Table 11 — Pages 33–35 (indices 32–34)
        # Participant Consent Signature Block
        # -------------------------------------------------------------------
        t_num = 11
        title = "Participant Consent Signature Block"
        pages_str = "33-35"
        rows = merge_grid_pages(pdf, [32, 33, 34], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [32, 33, 34])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Consent Signatures", df,
            "Participant signature block for informed consent — includes name, date, signature fields."
        ))

        # -------------------------------------------------------------------
        # Table 12 — Pages 35–36 (indices 34–35)
        # Witness and Investigator Signature Block
        # -------------------------------------------------------------------
        t_num = 12
        title = "Witness and Investigator Signature Block"
        pages_str = "35-36"
        rows = merge_grid_pages(pdf, [34, 35], table_idx=0)
        if rows and len(rows) >= 2:
            df = rows_to_df(rows)
        else:
            df = merge_word_pages(pdf, [34, 35])
        metadata_list.append(write_table_file(
            output_dir, t_num, title, pages_str,
            "Consent Signatures", df,
            "Witness and investigator signature block confirming completion of the consent process."
        ))

    # Save metadata JSON
    metadata_path = output_dir / "ICFs_tables_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=4, ensure_ascii=False)
    print(f"\n  \u2713 Metadata saved to: {metadata_path.name}")

    output_files = list(output_dir.glob("Table_*.md"))
    print(f'\n{"="*60}')
    print(f'\u2705 ICFs extraction complete: {len(output_files)} table files + metadata JSON')
    print(f'   Output: {output_dir}')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    input_pdf_path = Path("Input documents for CSR/ICFs.pdf")
    output_base = Path("artifacts/extracted_tables")
    process_icfs_tables(input_pdf_path, output_base)
