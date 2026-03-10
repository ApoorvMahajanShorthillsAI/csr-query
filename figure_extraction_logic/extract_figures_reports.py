"""
Figure Extraction: Reports (lab and tech).pdf
Method: Manual-Pattern
- 12 figures across pages 23, 24, 61, 62 (x2), 64 (x2), 65, 66, 82, 83, 84.
- Uses bbox crop for each figure. Page 62 has two separate figures.
"""
import json
import pdfplumber
from pathlib import Path


REPORTS_FIGURE_MAP = [
    {
        "figure_id": "Reports_Fig_23_1",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 23,
        "filename": "Reports_pg23.png",
        "figure_label": "Figure 1",
        "title": "Figure 1 ALC-0315 structure",
        "description": "Figure 1 ALC-0315 structure",
        "bbox": [0.0, 0.0, 595.32, 668.0],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_24_2",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 24,
        "filename": "Reports_pg24.png",
        "figure_label": "Figure 2",
        "title": "Figure 2 ALC-0159 structure",
        "description": "Figure 2 ALC-0159 structure",
        "bbox": [0.0, 514.79, 595.32, 610.29],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_61_3",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 61,
        "filename": "Reports_pg61.png",
        "figure_label": "Figure 3",
        "title": "Figure 3: BNT162b1 \u2013 Functional 50% SARS-CoV-2 neutralizing antibody titers (VN50) \u2013 IMM",
        "description": "Figure 3: BNT162b1 \u2013 Functional 50% SARS-CoV-2 neutralizing antibody titers (VN50) \u2013 IMM\nVN50 titers with 95% confidence intervals are shown for younger participants (aged 18 to 55 years) immunized with\n1, 10, 30, 50, or 60 \u03bcg BNT162b1.",
        "bbox": [0.0, 198.90, 595.32, 503.50],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_62_4",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 62,
        "filename": "Reports_pg62_1.png",
        "figure_label": "Figure 4",
        "title": "Figure 4: BNT162b2 \u2013 Functional 50% SARS-CoV-2 neutralizing antibody titres (VN50) \u2013 IMM",
        "description": "Figure 4: BNT162b2 \u2013 Functional 50% SARS-CoV-2 neutralizing antibody titres (VN50) \u2013 IMM",
        "bbox": [0.0, 65.90, 595.32, 354.58],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_62_custom",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 62,
        "filename": "Reports_pg62_custom_neutralisation.png",
        "figure_label": "Unnumbered Figure",
        "title": "Neutralisation of different spike protein mutants",
        "description": "Neutralisation of different spike protein mutants",
        "bbox": [0.0, 367.31, 595.32, 714.52],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_64_5",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 64,
        "filename": "Reports_pg64_1.png",
        "figure_label": "Figure 5",
        "title": "Figure 5. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2",
        "description": "Figure 5. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2\nDoses, 21 Days Apart \u2013 18-55 Years of Age \u2013 BNT162b1 \u2013 Evaluable Immunogenicity Population",
        "bbox": [0.0, 100.90, 595.32, 402.35],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_64_6",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 64,
        "filename": "Reports_pg64_2.png",
        "figure_label": "Figure 6",
        "title": "Figure 6. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2",
        "description": "Figure 6. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2\nDoses, 21 Days Apart\u2013 65-85 Years of Age \u2013 BNT162b1 \u2013 Evaluable Immunogenicity Population",
        "bbox": [0.0, 398.50, 595.32, 702.34],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_65_7",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 65,
        "filename": "Reports_pg65.png",
        "figure_label": "Figure 7",
        "title": "Figure 7. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2",
        "description": "Figure 7. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2\nDoses, 21 Days Apart \u2013 18-55 Years of Age \u2013 BNT162b2 \u2013 Evaluable Immunogenicity Population",
        "bbox": [0.0, 170.90, 595.32, 541.47],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_66_8",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 66,
        "filename": "Reports_pg66.png",
        "figure_label": "Figure 8",
        "title": "Figure 8. Geometric Mean Titres and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2",
        "description": "Figure 8. Geometric Mean Titres and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2\nDoses, 21 Days Apart \u2013 65-85 Years of Age \u2013 BNT162b2 \u2013 Evaluable Immunogenicity Population",
        "bbox": [0.0, 65.90, 595.32, 463.48],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_82_9",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 82,
        "filename": "Reports_pg82.png",
        "figure_label": "Figure 9",
        "title": "Figure 9. Cumulative Incidence Curves for the First COVID-19 Occurrence After Dose 1 \u2013 Dose 1 All-Available Efficacy Population",
        "description": "Figure 9. Cumulative Incidence Curves for the First COVID-19 Occurrence After Dose 1 \u2013 Dose 1 All-Available Efficacy Population",
        "bbox": [0.0, 376.75, 595.32, 723.65],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_83_10",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 83,
        "filename": "Reports_pg83.png",
        "figure_label": "Figure 10",
        "title": "Figure 10. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay \u2013 NT50 \u2013 Phase 2 \u2013 Dose 2 Evaluable Immunogenicity Population",
        "description": "Figure 10. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay \u2013 NT50 \u2013 Phase 2 \u2013 Dose 2 Evaluable Immunogenicity Population",
        "bbox": [0.0, 310.90, 595.32, 631.54],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
    {
        "figure_id": "Reports_Fig_84_11",
        "source_pdf": "Reports (lab and tech).pdf",
        "page_number": 84,
        "filename": "Reports_pg84.png",
        "figure_label": "Figure 11",
        "title": "Figure 11. Geometric Mean Concentrations and 95% CI: S1-Binding IgG Level Assay \u2013 Phase 2 Dose 2 Evaluable Immunogenicity Population",
        "description": "Figure 11. Geometric Mean Concentrations and 95% CI: S1-Binding IgG Level Assay \u2013 Phase 2 Dose 2 Evaluable Immunogenicity Population",
        "bbox": [0.0, 65.90, 595.32, 476.43],
        "extraction_info": {"method": "Manual-Pattern", "timestamp": "2026-03-05T20:35:00Z"}
    },
]

DPI = 150


def crop_and_save(page, bbox_pts, out_path: Path):
    x0, y0, x1, y1 = bbox_pts
    img = page.to_image(resolution=DPI).original
    sx = img.size[0] / float(page.width)
    sy = img.size[1] / float(page.height)
    box = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
    img.crop(box).save(str(out_path), format="PNG")


def process_reports_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "Reports (lab and tech)"
    out_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for entry in REPORTS_FIGURE_MAP:
            page = pdf.pages[entry["page_number"] - 1]
            out_path = out_dir / entry["filename"]
            try:
                crop_and_save(page, entry["bbox"], out_path)
                print(f"  Saved {entry['filename']}")
            except Exception as e:
                print(f"  ERROR saving {entry['filename']}: {e}")

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump(REPORTS_FIGURE_MAP, f, indent=2, ensure_ascii=False)
    print(f"  Saved figure_analysis.json ({len(REPORTS_FIGURE_MAP)} figures)")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\Reports (lab and tech).pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_reports_figures(p, b)
