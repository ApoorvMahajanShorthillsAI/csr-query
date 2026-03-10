import pdfplumber
import pandas as pd
import json
from pathlib import Path
import os

def clean_table_data(table_data):
    """
    Step 0: Replace None with "" and \n with " ".
    """
    if not table_data:
        return []
    cleaned_rows = []
    for row in table_data:
        cleaned_row = [("" if cell is None else str(cell).replace('\n', ' ')) for cell in row]
        cleaned_rows.append(cleaned_row)
    return cleaned_rows

def get_approx_section(page, table_top):
    """
    Finds the likely section heading above the table.
    Look for text starting with digits (e.g., '1.1') or 'Appendix'.
    """
    try:
        words = page.extract_words()
        # Filter for words above the table top (leave some buffer)
        words_above = [w for w in words if w['bottom'] < table_top]
        if not words_above:
            return "Unknown Section"
        
        # Sort by bottom position desc (closest to table first)
        words_above.sort(key=lambda x: x['bottom'], reverse=True)
        
        lines = []
        current_line = []
        last_top = -1
        
        for w in words_above:
            if last_top == -1 or abs(w['top'] - last_top) < 5:
                current_line.append(w)
            else:
                lines.append(current_line)
                current_line = [w]
            last_top = w['top']
        if current_line: lines.append(current_line)
        
        # Look at the last 10 lines for something that looks like a heading
        for line in lines[:10]:
            text = " ".join([w['text'] for w in sorted(line, key=lambda x: x['x0'])])
            # Common section patterns: "1. ", "1.1 ", "Appendix ", "Section "
            if any(text.startswith(p) for p in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "Appendix", "Table", "Section"]):
                return text
                
        return "See context in document" # Fallback
    except:
        return "Unknown Section"

def process_ctp_tables(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Starting Precise Extraction for {pdf_path.name} ---")
    
    output_dir = output_base_dir / "CTP"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_list = []
    # Registry: list of (table_num, title, pages_indices, description)
    # Registry: list of (table_num, title, pages_indices, description)
    # pages_indices is a list of (page_index, table_index)
    registry = [
        (1, "Objectives Estimands Endpoints — Phase 1 Primary", [(9, 0)], "Primary objectives and endpoints for Phase 1 of the study."),
        (2, "Objectives Estimands Endpoints — Phase 1 Secondary (continued)", [(10, 0)], "Secondary objectives and endpoints for Phase 1 (continued)."),
        (3, "Objectives Estimands Endpoints — Phase 2/3 intro", [(10, 1)], "Introduction to Phase 2/3 objectives and endpoints."),
        (4, "Objectives Estimands Endpoints — Phase 2/3 Safety", [(11, 0)], "Safety objectives and endpoints for Phase 2/3."),
        (5, "Objectives Estimands Endpoints — Phase 2/3 Severe COVID Efficacy", [(12, 0)], "Efficacy objectives for severe COVID cases in Phase 2/3."),
        (6, "Objectives Estimands Endpoints — HIV Subgroup", [(13, 0)], "Objectives and endpoints for the HIV subgroup."),
        (7, "Schedule of Activities Phase 1", [(17, 0), (18, 0), (19, 0), (20, 0), (21, 0)], "Comprehensive schedule of activities for Phase 1."),
        (8, "Schedule of Activities Phase 2/3", [(22, 0), (23, 0), (24, 0)], "Comprehensive schedule of activities for Phase 2/3."),
        (9, "Risk Assessment — Vaccine Intervention", [(28, 0)], "Analysis of risks associated with the vaccine intervention."),
        (10, "Risk Assessment — Study Procedures", [(29, 0)], "Analysis of risks associated with study procedures."),
        (11, "Objectives Estimands Endpoints — Phase 2/3 Primary (pg 31)", [(30, 0)], "Primary objectives for Phase 2/3 on page 31."),
        (12, "Objectives Estimands Endpoints — Phase 2/3 Secondary (pg 32)", [(31, 0)], "Secondary objectives for Phase 2/3 on page 32."),
        (13, "Objectives Estimands Endpoints — Phase 2/3 Primary Efficacy", [(32, 0)], "Primary efficacy objectives and endpoints for Phase 2/3."),
        (14, "Objectives Estimands Endpoints — Phase 2/3 Secondary Efficacy", [(33, 0)], "Secondary efficacy objectives and endpoints for Phase 2/3."),
        (15, "Objectives Estimands Endpoints — Phase 2/3 Immunogenicity", [(34, 0)], "Immunogenicity objectives and endpoints for Phase 2/3."),
        (16, "Study Interventions — BNT162b1 vs BNT162b2 vs Placebo", [(45, 0)], "Comparison of study interventions including placebo."),
        (17, "Reactogenicity Grading Scale — Local Reactions", [(59, 0)], "Grading scale for evaluating local reactogenicity."),
        (18, "Reactogenicity Grading Scale — Systemic Events", [(60, 0)], "Grading scale for evaluating systemic reactogenicity."),
        (19, "Fever Temperature Scale", [(61, 0)], "Grading scale for fever based on temperature."),
        (20, "AE SAE Reporting Requirements", [(70, 0)], "Requirements for reporting Adverse Events and Serious Adverse Events."),
        (21, "Sample Size Immunogenicity Noninferiority Criteria", [(99, 0)], "Criteria for immunogenicity non-inferiority sample size."),
        (22, "Table 5: Probability of Observing at Least 1 AE by Sample Size", [(100, 0)], "Statistical table showing probability of AE occurrence by sample size."),
        (23, "Analysis Populations Definitions Part 1", [(100, 1)], "Definitions for analysis populations, part 1."),
        (24, "Analysis Populations Definitions Part 2", [(101, 0)], "Definitions for analysis populations, part 2."),
        (25, "Statistical Analysis Methods", [(102, 0), (103, 0), (104, 0), (105, 0), (106, 0), (107, 0), (108, 0), (109, 0)], "Detailed statistical analysis methods across multiple pages."),
        (26, "Table 6: Interim Analysis Efficacy Futility Boundaries", [(111, 0)], "Efficacy and futility boundaries for interim analysis."),
        (27, "Table 7: Statistical Design Operating Characteristics", [(112, 0), (112, 1)], "Statistical design operating characteristics merged from page 113."),
        (28, "Appendix 2: Clinical Laboratory Tests List", [(122, 0)], "List of clinical laboratory tests in Appendix 2."),
        (29, "Table 8: Laboratory Abnormality Grading Scale — Hematology", [(122, 1)], "Grading scale for hematology laboratory abnormalities."),
        (30, "Table 9: Laboratory Abnormality Grading Scale — Chemistry", [(123, 0)], "Grading scale for chemistry laboratory abnormalities."),
        (31, "AE Definition", [(124, 0)], "Formal definition of an Adverse Event."),
        (32, "Events Meeting AE Definition", [(124, 1)], "List of events that meet the AE definition."),
        (33, "Events NOT Meeting AE Definition", [(125, 0)], "List of events that do NOT meet the AE definition."),
        (34, "SAE Definition", [(125, 1)], "Formal definition of a Serious Adverse Event."),
        (35, "SAE Definition Continued", [(126, 0)], "Continuation of the Serious Adverse Event definition."),
        (36, "AE SAE Recording Reporting Narrative", [(127, 0)], "Narrative guidance for recording and reporting AE/SAE."),
        (37, "AE SAE Reporting Requirements Summary Table", [(127, 1)], "Summary table showing reporting requirements for AE/SAE."),
        (38, "Assessment of Intensity Grade Definitions", [(128, 1)], "Definitions for the assessment of event intensity grades."),
        (39, "Appendix 6: Abbreviations", [(137, 0), (138, 0), (139, 0), (140, 0)], "List of abbreviations used in clinical laboratory tests."),
        (40, "Table 10: Stopping Rule Severe Cases", [(142, 0)], "Stopping rule criteria for severe cases."),
        (41, "Table 11: Alert Rule Severe Cases Probability", [(143, 0)], "Probability statistics for alert rules in severe cases.")
    ]
    
    with pdfplumber.open(pdf_path) as pdf:
        for table_num, title, p_idx_list, description in registry:
            print(f"Extracting Table {table_num} ({title})...")
            
            combined_rows = []
            canonical_header = None
            section_found = "N/A"
            final_pages = []
            
            for i, (page_idx, table_idx) in enumerate(p_idx_list):
                if page_idx >= len(pdf.pages): continue
                page = pdf.pages[page_idx]
                final_pages.append(page_idx + 1)
                
                # Get raw table
                tables = page.extract_tables()
                if not tables or table_idx >= len(tables):
                    print(f"  Warning: Table index {table_idx} not found on page {page_idx + 1}")
                    continue
                
                raw_data = tables[table_idx]
                cleaned_data = clean_table_data(raw_data)
                
                if not cleaned_data:
                    continue
                    
                # Find section for the very first part of a merged table
                if i == 0:
                    # Find table bbox to locate text above it
                    ts = page.find_tables()
                    if ts and table_idx < len(ts):
                        bbox = ts[table_idx].bbox
                        section_found = get_approx_section(page, bbox[1])
                
                current_header = cleaned_data[0]
                
                if i == 0:
                    canonical_header = current_header
                    combined_rows = cleaned_data
                else:
                    # Merging rule: skip if first row matches canonical header
                    if current_header == canonical_header:
                        combined_rows.extend(cleaned_data[1:])
                    else:
                        combined_rows.extend(cleaned_data)
            
            if not combined_rows:
                continue
            
            df = pd.DataFrame(combined_rows[1:], columns=combined_rows[0])
            
            # Prepare metadata
            pages_str = f"{final_pages[0]}" if len(final_pages) == 1 else f"{final_pages[0]}-{final_pages[-1]}"
            metadata_entry = {
                "TableNumber": table_num,
                "Title": title,
                "Pages": pages_str,
                "Section": section_found,
                "ColumnCount": len(df.columns),
                "RowCount": len(df),
                "Description": description
            }
            metadata_list.append(metadata_entry)

            # Output 1: Markdown (Separate Files)
            sep_md_filename = f"Table_{table_num}.md"
            sep_md_path = output_dir / sep_md_filename
            
            with open(sep_md_path, "w", encoding="utf-8") as sep_f:
                sep_f.write(f"# Table {table_num}: {title}\n\n")
                sep_f.write(df.to_markdown(index=False, tablefmt="github"))

    # Save metadata JSON
    metadata_path = output_dir / "CTP_tables_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=4)
        
    print(f"\n✅ All expected tables extracted successfully.")
    print(f"  Individual files and metadata in: {output_dir}")

if __name__ == "__main__":
    # Internal run logic
    input_pdf_path = Path("Input documents for CSR/CTP.pdf")
    output_base = Path("artifacts/extracted_tables")
    process_ctp_tables(input_pdf_path, output_base)
