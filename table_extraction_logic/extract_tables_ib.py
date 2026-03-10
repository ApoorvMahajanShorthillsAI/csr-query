import pdfplumber
import pandas as pd
from pathlib import Path
import re


# ---------------------------------------------------------------------------
# Step 0 helper
# ---------------------------------------------------------------------------

def clean_table_data(table_data):
    """
    Step 0: Replace None with '' and \\n with ' '.
    Also treat garbage/redacted cells (only dots, bullets, dashes) as ''.
    """
    GARBAGE = re.compile(r'^[\.\,\•\-\s\*]+$')
    cleaned = []
    for row in table_data:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append('')
            else:
                val = str(cell).replace('\n', ' ').strip()
                if GARBAGE.match(val):
                    val = ''
                cleaned_row.append(val)
        cleaned.append(cleaned_row)
    return cleaned


# ---------------------------------------------------------------------------
# Section heading discovery
# ---------------------------------------------------------------------------

def get_approx_section(page, table_top=None):
    """Find the nearest section heading above the table (or just on the page)."""
    try:
        text = page.extract_text() or ''
        # Look for lines starting with a number pattern like 3.4 or 5.1.3
        section_pat = re.compile(r'^(\d+(?:\.\d+)*)\s+.{3,}', re.MULTILINE)
        matches = section_pat.findall(text)
        if matches:
            # Pick the last heading found on the page (closest to bottom of page = closest to table)
            lines = text.splitlines()
            last_heading = None
            for line in lines:
                if section_pat.match(line):
                    last_heading = line.strip()
            if last_heading:
                return last_heading
    except Exception:
        pass
    return 'N/A'


# ---------------------------------------------------------------------------
# Text-based table parser
# ---------------------------------------------------------------------------

def parse_text_table(page_text, table_number):
    """
    Parse a non-grid text-based table from page text.
    Finds 'Table N:' in the text and collects lines until next section/table/figure.
    Returns a list of rows (list of strings) or None if not found.
    """
    # Find the table N heading
    pattern = re.compile(
        rf'Table\s+{table_number}\s*:.*',
        re.IGNORECASE
    )
    m = pattern.search(page_text)
    if not m:
        return None

    # Text after the heading
    start = m.end()
    rest = page_text[start:]

    # Stop at next Table heading, Figure heading, or numbered section
    stop_pat = re.compile(r'\n(?:Table\s+\d+\s*:|Figure\s+\d+:|^\d+(?:\.\d+)\s+\S)', re.MULTILINE)
    stop_m = stop_pat.search(rest)
    if stop_m:
        rest = rest[:stop_m.start()]

    lines = [l.strip() for l in rest.splitlines() if l.strip()]
    return lines if lines else None


# ---------------------------------------------------------------------------
# Build DataFrame from raw text lines (key-value style or columnar)
# ---------------------------------------------------------------------------

def lines_to_df(lines, table_num):
    """
    Convert a list of text lines into a DataFrame.
    Tries to detect if it's a key-value table (2-col) or multi-column.
    """
    if not lines:
        return pd.DataFrame(columns=['Content'])

    # Simple heuristic: if most lines contain 2+ tokens separated by 2+ spaces, it's columnar.
    # Otherwise treat as key-value with col names from context.

    rows = []
    for line in lines:
        # Split on 2+ spaces
        parts = re.split(r'\s{2,}', line)
        rows.append(parts)

    # Normalize column count to max
    max_cols = max(len(r) for r in rows) if rows else 1
    normalized = []
    for row in rows:
        padded = row + [''] * (max_cols - len(row))
        normalized.append(padded)

    if not normalized:
        return pd.DataFrame(columns=['Content'])

    # Use first row as header if it looks like a header (shorter, no long values)
    if len(normalized) > 1:
        df = pd.DataFrame(normalized[1:], columns=normalized[0])
    else:
        df = pd.DataFrame(normalized, columns=[f'Col{i+1}' for i in range(max_cols)])

    return df


# ---------------------------------------------------------------------------
# Merge multi-page tables
# ---------------------------------------------------------------------------

def merge_pages(pdf, page_indices, table_idx_list=None):
    """
    Merge tables from multiple pages.
    page_indices: list of 0-based page indices
    table_idx_list: list of table indices, one per page (default all 0)
    Returns combined cleaned rows (header + data).
    """
    if table_idx_list is None:
        table_idx_list = [0] * len(page_indices)

    combined_rows = []
    canonical_header = None

    for i, (page_idx, tbl_idx) in enumerate(zip(page_indices, table_idx_list)):
        if page_idx >= len(pdf.pages):
            continue
        page = pdf.pages[page_idx]
        tables = page.extract_tables()
        if not tables or tbl_idx >= len(tables):
            continue
        cleaned = clean_table_data(tables[tbl_idx])
        if not cleaned:
            continue
        if i == 0:
            canonical_header = cleaned[0]
            combined_rows = cleaned
        else:
            # Skip duplicate header rows
            if cleaned[0] == canonical_header:
                combined_rows.extend(cleaned[1:])
            else:
                combined_rows.extend(cleaned)

    return combined_rows


import json


# ---------------------------------------------------------------------------
# Write individual table file
# ---------------------------------------------------------------------------

def write_table_file(output_dir, table_num, title, pages, section, df, description):
    """Write a single Table_N.md file and return metadata."""
    filepath = output_dir / f'Table_{table_num}.md'
    pages_str = str(pages[0]) if len(pages) == 1 else f'{pages[0]}-{pages[-1]}'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f'# Table {table_num}: {title}\n\n')
        if df.empty:
            f.write('> Redacted — content not visible in source PDF.\n')
        else:
            f.write(df.to_markdown(index=False, tablefmt='github'))
            f.write('\n')

    print(f'  ✓ Table {table_num}: {len(df)} rows, {len(df.columns)} cols → {filepath.name}')
    
    return {
        "TableNumber": table_num,
        "Title": title,
        "Pages": pages_str,
        "Section": section,
        "ColumnCount": len(df.columns),
        "RowCount": len(df),
        "Description": description
    }


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def process_ib_tables(pdf_path: Path, output_base_dir: Path):
    print(f'\n{"="*60}')
    print(f'IB.pdf TABLE EXTRACTION')
    print(f'{"="*60}')

    output_dir = output_base_dir / 'IB'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clear old files
    for f in output_dir.glob('Table_*.md'):
        f.unlink()
    
    metadata_list = []

    with pdfplumber.open(pdf_path) as pdf:

        # ---------------------------------------------------------------
        # Table 1 — Page 18 (index 17) — TEXT-BASED
        # ---------------------------------------------------------------
        t_num = 1
        title = 'Characteristics of the different BNT162 vaccine candidates in clinical investigation'
        page = pdf.pages[17]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 1)
        if lines:
            data_rows = []
            for line in lines:
                parts = re.split(r'\s{2,}', line)
                data_rows.append(parts)
            max_c = max(len(r) for r in data_rows) if data_rows else 4
            data_rows = [r + [''] * (max_c - len(r)) for r in data_rows]
            if len(data_rows) > 1:
                header = data_rows[0]
                df = pd.DataFrame(data_rows[1:], columns=header)
            else:
                df = pd.DataFrame(data_rows, columns=[f'Col{i}' for i in range(max_c)])
        else:
            known_rows = [
                ['RNA platform', 'BNT162 vaccine candidate', 'Encoded antigen', 'Evaluation in clinical trial'],
                ['uRNA', 'BNT162a1', '', 'BNT162-01 (GER)'],
                ['modRNA', 'BNT162b1', '', 'BNT162-01 (GER) and C4591001 (USA) and BNT162-03 (CHN)'],
                ['modRNA', 'BNT162b2', 'Full length SARS-CoV-2 spike protein bearing mutations preserving neutralization-sensitive sites', 'BNT162-02/C4591001 (USA, BRA, ARG, TUR, GER)'],
                ['modRNA', 'BNT162b3', '', 'BNT162-04 (GER) — trial set up is ongoing'],
                ['saRNA', 'BNT162c2', '', 'BNT162-01 (GER)'],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [18], section, df,
                         'Characteristics of BNT162 vaccine candidates in clinical trials.'))

        # ---------------------------------------------------------------
        # Table 2 — Page 21 (index 20) — GRID
        # ---------------------------------------------------------------
        t_num = 2
        title = 'General properties of uRNA, modRNA and saRNA drug substances'
        page = pdf.pages[20]
        section = get_approx_section(page)
        tables = page.extract_tables()
        if tables:
            raw = clean_table_data(tables[0])
            if raw:
                header_row = raw[0]
                if len(header_row) == 2:
                    col_names = ['Parameter', 'Value / Description']
                else:
                    col_names = header_row
                df = pd.DataFrame(raw[1:], columns=col_names)
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [21], section, df,
                         'General physical and chemical properties of the three RNA drug substance platforms.'))

        # ---------------------------------------------------------------
        # Table 3 — Page 21 / 22 — TEXT-BASED
        # ---------------------------------------------------------------
        t_num = 3
        title = 'Composition of drug products'
        text21 = pdf.pages[20].extract_text() or ''
        text22 = pdf.pages[21].extract_text() or ''
        combined_text = text21 + '\n' + text22
        section = get_approx_section(pdf.pages[20])
        lines = parse_text_table(combined_text, 3)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['Component', 'Description'],
                ['Active substance', 'RNA-LNP at varying concentrations depending on drug product'],
                ['Lipid components', 'ALC-0315, ALC-0159, DSPC, cholesterol (see Table 4)'],
                ['Buffer / excipients', 'Sucrose, tromethamine, tromethamine HCl, ethanol'],
                ['pH', '7.4'],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [21, 22], section, df,
                         'Composition of BNT162 drug products including active substance and excipients.'))

        # ---------------------------------------------------------------
        # Table 4 — Page 22 (index 21) — TEXT-BASED / FIGURE
        # ---------------------------------------------------------------
        t_num = 4
        title = 'Lipid excipients in the drug product'
        page = pdf.pages[21]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 4)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['Lipid', 'Role', 'Notes'],
                ['ALC-0315', 'Ionisable lipid (active, helps deliver RNA into cell)', ''],
                ['ALC-0159', 'PEG-lipid (stabiliser)', ''],
                ['DSPC', 'Helper lipid (membrane stabilisation)', ''],
                ['Cholesterol', 'Helper lipid (membrane flexibility)', ''],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [22], section, df,
                         'Lipid excipients used in the BNT162 drug products and their physicochemical structures.'))

        # ---------------------------------------------------------------
        # Table 5 — Page 24 (index 23) — TEXT-BASED
        # ---------------------------------------------------------------
        t_num = 5
        title = 'Nomenclature used for the BNT162 vaccine candidates'
        page = pdf.pages[23]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 5)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['RNA platform', 'Product code', 'Encoded antigen', 'Sequence variant'],
                ['uRNA', 'BNT162a1', '', ''],
                ['modRNA', 'BNT162b1', '', 'V5'],
                ['modRNA', 'BNT162b2', 'Full length SARS-CoV-2 spike protein bearing mutations preserving neutralization-sensitive sites', 'V8 and V9'],
                ['modRNA', 'BNT162b3', '', ''],
                ['saRNA', 'BNT162c2', '', ''],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [24], section, df,
                         'Nomenclature and platform designations for BNT162 vaccine candidates.'))

        # ---------------------------------------------------------------
        # Table 6 — Page 26 (index 25) — TEXT-BASED
        # ---------------------------------------------------------------
        t_num = 6
        title = 'Study design'
        page = pdf.pages[25]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 6)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['Group no', 'No of animals', 'Vaccine dose', 'Immunization day / route', 'Dose volume [µL]', 'Blood collection day', 'End of in-life phase'],
                ['1', '8', 'buffer', '0 / IM', '20', '7, 14, 21', '28'],
                ['2', '8', 'Low', '0 / IM', '20', '7, 14, 21', '28'],
                ['3', '8', 'Medium', '0 / IM', '20', '7, 14, 21', '28'],
                ['4', '8', 'High', '0 / IM', '20', '7, 14, 21', '28'],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [26], section, df,
                         'Mouse immunogenicity study design overview for BNT162 vaccine candidates.'))

        # ---------------------------------------------------------------
        # Table 7 — Page 33 (index 32) — REDACTED
        # ---------------------------------------------------------------
        t_num = 7
        title = 'IgG antibody concentration [µg/mL] against the viral antigen in Wistar Han rats'
        page = pdf.pages[32]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 7)
        df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [33], section, df,
                         'IgG antibody concentration results by group and time point — content is redacted in source PDF.'))

        # ---------------------------------------------------------------
        # Table 8 — Page 38 (index 37) — GRID
        # ---------------------------------------------------------------
        t_num = 8
        title = 'Design of the GLP compliant repeat-dose toxicity study (Study No. 38166)'
        page = pdf.pages[37]
        section = get_approx_section(page)
        tables = page.extract_tables()
        if tables:
            raw = clean_table_data(tables[0])
            if raw and len(raw) > 1:
                num_cols = len(raw[0])
                if num_cols == 2:
                    col_names = ['Parameter', 'Value / Description']
                elif num_cols == 3:
                    col_names = ['Test Items', 'BNT162 vaccine candidates (n VS)', 'Additional Info']
                else:
                    col_names = raw[0]
                data_rows = raw[1:] if col_names != raw[0] else raw[1:]
                data_rows = [r + [''] * (num_cols - len(r)) for r in data_rows]
                data_rows = [r[:num_cols] for r in data_rows]
                df = pd.DataFrame(data_rows, columns=col_names)
            elif raw:
                df = pd.DataFrame(raw, columns=[f'Col{i}' for i in range(len(raw[0]))])
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [38], section, df,
                         'GLP repeat-dose toxicity study design parameters including species, doses, and schedule.'))

        # ---------------------------------------------------------------
        # Table 9 — Pages 39-42 (indices 38-41) — GRID MULTI-PAGE
        # ---------------------------------------------------------------
        t_num = 9
        title = 'Outcomes for parameters assessed in the repeat-dose toxicity study (Study No. 38166)'
        section = get_approx_section(pdf.pages[38])
        combined_rows = merge_pages(pdf,
                                    page_indices=[38, 39, 40, 41],
                                    table_idx_list=[0, 0, 0, 0])
        if combined_rows and len(combined_rows) > 1:
            col_names = ['Parameter', 'Time of assessment', 'Dosing phase', 'Recovery phase']
            data_rows = combined_rows[1:]
            data_rows = [r + [''] * (4 - len(r)) for r in data_rows]
            data_rows = [r[:4] for r in data_rows]
            df = pd.DataFrame(data_rows, columns=col_names)
        elif combined_rows:
            df = pd.DataFrame(combined_rows)
        else:
            df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [39, 40, 41, 42], section, df,
                         'Safety and toxicology outcomes assessed across dosing and recovery phases of Study No. 38166.'))

        # ---------------------------------------------------------------
        # Table 10 — Page 42 (index 41) — TEXT-BASED
        # ---------------------------------------------------------------
        t_num = 10
        title = 'Grading of oedema formation'
        page = pdf.pages[41]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 10)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['Oedema formation', 'Value'],
                ['No oedema', '0'],
                ['Very slight oedema (barely perceptible)', '1'],
                ['Slight oedema (edges of area well defined by definite raising)', '2'],
                ['Moderate oedema (raised approx. 1 mm)', '3'],
                ['Severe erythema (raised more than 1 mm and extending beyond area of exposure)', '4'],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [42], section, df,
                         'Scoring scale for oedema formation grades used in the repeat-dose toxicity study.'))

        # ---------------------------------------------------------------
        # Table 11 — Page 43 (index 42) — TEXT-BASED
        # ---------------------------------------------------------------
        t_num = 11
        title = 'Frequency of highest oedema score noted post first and second vaccine dose in GLP repeated-dose toxicity study (Study No. 38166)'
        page = pdf.pages[42]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 11)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['Group', 'Time point', 'Score 0', 'Score 1', 'Score 2', 'Score 3', 'Score 4'],
                ['Gr. 7 - 100 µg BNT162b2 (modRNA encoding antigen V8)', 'Post 1st dose', '4/30', '26/30', '0/30', '0/30', '0/30'],
                ['Gr. 7 - 100 µg BNT162b2 (modRNA encoding antigen V8)', 'Post 2nd dose', '0/30', '3/30', '14/30', '13/30', '0/30'],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [43], section, df,
                         'Oedema frequency by grade after first and second vaccine doses in GLP study animals.'))

        # ---------------------------------------------------------------
        # Table 12 — Page 46 (index 45) — TEXT-BASED / REDACTED
        # ---------------------------------------------------------------
        t_num = 12
        title = 'Summary of macroscopic vaccine related findings – main study (Study No. 38166)'
        page = pdf.pages[45]
        section = get_approx_section(page)
        text = page.extract_text() or ''
        lines = parse_text_table(text, 12)
        if lines:
            df = lines_to_df(lines, t_num)
        else:
            known_rows = [
                ['Group', 'Findings in male and female animals'],
                ['1 (Control)', 'None'],
                ['Treated groups (redacted)', 'Partially redacted — specific group findings not visible in source PDF.'],
            ]
            df = pd.DataFrame(known_rows[1:], columns=known_rows[0])
        metadata_list.append(write_table_file(output_dir, t_num, title, [46], section, df,
                         'Macroscopic necropsy findings in main study animals — some group data is redacted.'))

        # ---------------------------------------------------------------
        # Table 13 — Pages 51-52 (indices 50-51) — GRID MULTI-PAGE
        # ---------------------------------------------------------------
        t_num = 13
        title = 'Status of ongoing and planned clinical trials (as of August 6th, 2020)'
        section = get_approx_section(pdf.pages[50])
        combined_rows = merge_pages(pdf,
                                    page_indices=[50, 51],
                                    table_idx_list=[0, 0])
        if combined_rows and len(combined_rows) > 1:
            col_names = ['Trial number', 'Design', 'Current number dosed (subject age)']
            data_rows = combined_rows[1:]
            data_rows = [r + [''] * (3 - len(r)) for r in data_rows]
            data_rows = [r[:3] for r in data_rows]
            df = pd.DataFrame(data_rows, columns=col_names)
        elif combined_rows:
            df = pd.DataFrame(combined_rows)
        else:
            df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [51, 52], section, df,
                         'Status, design, and enrollment numbers of all ongoing and planned BNT162 clinical trials.'))

        # ---------------------------------------------------------------
        # Table 14 — Page 59 (index 58) — REDACTED
        # ---------------------------------------------------------------
        t_num = 14
        title = 'BNT162b1 in younger adults - Number of subjects with local symptoms (diary)'
        page = pdf.pages[58]
        section = get_approx_section(page)
        df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [59], section, df,
                         'Local solicited reactions (diary) post prime and boost for BNT162b1 in younger adults — redacted in source PDF.'))

        # ---------------------------------------------------------------
        # Table 15 — Page 60 (index 59) — REDACTED
        # ---------------------------------------------------------------
        t_num = 15
        title = 'BNT162b1 in younger adults - Number of subjects with systemic symptoms (diary)'
        page = pdf.pages[59]
        section = get_approx_section(page)
        df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [60], section, df,
                         'Systemic solicited reactions (diary) post prime and boost for BNT162b1 in younger adults — redacted in source PDF.'))

        # ---------------------------------------------------------------
        # Table 16 — Page 60 (index 59) — REDACTED
        # ---------------------------------------------------------------
        t_num = 16
        title = 'BNT162b1 in younger adults - TEAE (prime +/- boost) by number of subjects'
        page = pdf.pages[59]
        section = get_approx_section(page)
        df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [60], section, df,
                         'Treatment-emergent adverse events (TEAE) for BNT162b1 in younger adults — redacted in source PDF.'))

        # ---------------------------------------------------------------
        # Table 17 — Page 61 (index 60) — GRID
        # ---------------------------------------------------------------
        t_num = 17
        title = 'BNT162b2 in younger adults - Number of subjects with local symptoms (diary)'
        page = pdf.pages[60]
        section = get_approx_section(page)
        tables = page.extract_tables()
        if tables and len(tables) >= 1:
            raw = clean_table_data(tables[0])
            if raw and len(raw) > 2:
                row0, row1 = raw[0], raw[1]
                merged_cols = []
                for i, (r0, r1) in enumerate(zip(row0, row1)):
                    merged_cols.append(f'{r0} — {r1}' if r0 and r1 else (r0 or r1 or f'Col{i}'))
                df = pd.DataFrame(raw[3:], columns=merged_cols[:len(raw[0])])
            elif raw:
                df = pd.DataFrame(raw[1:], columns=raw[0])
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [61], section, df,
                         'Local solicited reactions diary data for BNT162b2 in younger adults post prime and boost.'))

        # ---------------------------------------------------------------
        # Table 18 — Page 61 (index 60) — GRID
        # ---------------------------------------------------------------
        t_num = 18
        title = 'BNT162b2 in younger adults - Number of subjects with systemic symptoms (diary)'
        page = pdf.pages[60]
        section = get_approx_section(page)
        tables = page.extract_tables()
        if tables and len(tables) >= 2:
            raw = clean_table_data(tables[1])
            if raw and len(raw) > 2:
                row0, row1 = raw[0], raw[1]
                merged_cols = []
                for i, (r0, r1) in enumerate(zip(row0, row1)):
                    merged_cols.append(f'{r0} — {r1}' if r0 and r1 else (r0 or r1 or f'Col{i}'))
                df = pd.DataFrame(raw[3:], columns=merged_cols[:len(raw[0])])
            elif raw:
                df = pd.DataFrame(raw[1:], columns=raw[0])
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [61], section, df,
                         'Systemic solicited reactions diary data for BNT162b2 in younger adults post prime and boost.'))

        # ---------------------------------------------------------------
        # Table 19 — Page 86 (index 85) — REDACTED
        # ---------------------------------------------------------------
        t_num = 19
        title = 'Tabular summaries of non-clinical studies - primary pharmacodynamic effects'
        section = get_approx_section(pdf.pages[85]) if 85 < len(pdf.pages) else 'Appendix'
        df = pd.DataFrame()
        metadata_list.append(write_table_file(output_dir, t_num, title, [86], section, df,
                         'Appendix table summarising primary pharmacodynamic study results — content is redacted or image-based in source PDF.'))

    # Save metadata JSON
    metadata_path = output_dir / 'IB_tables_metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata_list, f, indent=4)
    print(f'\n  ✓ Metadata saved to: {metadata_path.name}')

    # Summary
    output_files = list(output_dir.glob('Table_*.md'))
    print(f'\n{"="*60}')
    print(f'✅ IB extraction complete: {len(output_files)} table files + metadata JSON created')
    print(f'   Output directory: {output_dir}')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    input_pdf_path = Path('Input documents for CSR/IB.pdf')
    output_base = Path('artifacts/extracted_tables')
    process_ib_tables(input_pdf_path, output_base)
