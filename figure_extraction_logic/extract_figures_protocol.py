"""
Figure Extraction: Protocol Devaition log.pdf
Method: Mixed — Manual-Portrait, Manual-Portrait-Stitched, Manual-Landscape-Crop
- Portrait pages (18,22,24,25,26,27,35,36,37): standard bbox crop.
- Landscape pages (40,41,58,81-86): rotate 90° then crop full page.
- Page 23: stitched across two half-pages (portrait).
"""
import json
import pdfplumber
from pathlib import Path


# Entries with method "Manual-Landscape-Crop" use full-page landscape rendering;
# others use standard portrait bbox crop.
PROTOCOL_FIGURE_MAP = [
    {
        "figure_id": "Protocol_Fig_18_1.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 18,
        "filename": "Protocol Devaition log_pg18.png",
        "figure_label": "Figure 1.",
        "title": "Figure 1. Safety Evaluation Follow-Up Periods in Study C4591001",
        "description": "Figure 1. Safety Evaluation Follow-Up Periods in Study C4591001",
        "bbox": [0.0, 213.93, 612.0, 411.93],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_22_2.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 22,
        "filename": "Protocol Devaition log_pg22.png",
        "figure_label": "Figure 2.",
        "title": "Figure 2.  Frequency and Magnitude of BNT162b2-induced CD4+ and CD8+ T Cell Responses",
        "description": "Figure 2.  Frequency and Magnitude of BNT162b2-induced CD4+ and CD8+ T Cell Responses\nPBMCs of BNT162b2-immunized participants were obtained on Day 1 (pre-prime) and on Day 29 (7 days post dose 2).",
        "bbox": [0.0, 334.38, 612.0, 639.47],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_23_3.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 23,
        "filename": "Protocol Devaition log_pg23.png",
        "figure_label": "Figure 3.",
        "title": "Figure 3.  S-Specific CD4+ T Cells Producing Each Cytokine as a Fraction of Total Cytokine-Producing S-specific CD4+ T Cells",
        "description": "Figure 3.  S-Specific CD4+ T Cells Producing Each Cytokine as a Fraction of Total Cytokine-Producing S-specific CD4+ T Cells",
        "bbox": [0.0, 199.98, 612.0, 724.29],
        "extraction_info": {"method": "Manual-Portrait-Stitched", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_24_4.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 24,
        "filename": "Protocol Devaition log_pg24.png",
        "figure_label": "Figure 4.",
        "title": "Figure 4. BNT162b2-Induced Virus Neutralization Titers",
        "description": "Figure 4. BNT162b2-Induced Virus Neutralization Titers",
        "bbox": [0.0, 333.09, 612.0, 603.51],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_25_5.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 25,
        "filename": "Protocol Devaition log_pg25.png",
        "figure_label": "Figure 5.",
        "title": "Figure 5. Breadth of BNT162b2-Induced Neutralization Against a Panel of Pseudovirus Spike Sequence Variants",
        "description": "Figure 5. Breadth of BNT162b2-Induced Neutralization Against a Panel of Pseudovirus Spike Sequence Variants",
        "bbox": [0.0, 65.58, 612.0, 393.93],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_26_6.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 26,
        "filename": "Protocol Devaition log_pg26.png",
        "figure_label": "Figure 6.",
        "title": "Figure 6. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2 Doses, 21 Days Apart \u2013 18-55 Years of Age \u2013 BNT162b2 \u2013 Evaluable Immunogenicity Population",
        "description": "Figure 6. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50 \u2013 Phase 1, 2 Doses, 21 Days Apart \u2013 18-55 Years of Age \u2013 BNT162b2 \u2013 Evaluable Immunogenicity Population",
        "bbox": [0.0, 282.93, 612.0, 611.73],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_27_7.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 27,
        "filename": "Protocol Devaition log_pg27.png",
        "figure_label": "Figure 7.",
        "title": "Figure 7. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50  \u2013 Phase 1, 2 Doses, 21 Days Apart \u2013 65-85 Years of Age \u2013 BNT162b2 \u2013 Evaluable Immunogenicity Population",
        "description": "Figure 7. Geometric Mean Titers and 95% CI: SARS-CoV-2 Neutralization Assay - NT50  \u2013 Phase 1, 2 Doses, 21 Days Apart \u2013 65-85 Years of Age \u2013 BNT162b2 \u2013 Evaluable Immunogenicity Population",
        "bbox": [0.0, 65.58, 612.0, 418.71],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_35_8.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 35,
        "filename": "Protocol Devaition log_pg35.png",
        "figure_label": "Figure 8.",
        "title": "Figure 8. Geometric Mean Titers: SARS-CoV-2 Neutralization Assay \u2013 NT50 \u2013 Evaluable Immunogenicity Population \u2013 Phase 2",
        "description": "Figure 8. Geometric Mean Titers: SARS-CoV-2 Neutralization Assay \u2013 NT50 \u2013 Evaluable Immunogenicity Population \u2013 Phase 2",
        "bbox": [0.0, 67.53, 612.0, 378.51],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_36_9.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 36,
        "filename": "Protocol Devaition log_pg36.png",
        "figure_label": "Figure 9.",
        "title": "Figure 9.  Participants Reporting Local Reactions, by Maximum Severity, Within 7 Days After Each Dose, by Age Group",
        "description": "Figure 9.  Participants Reporting Local Reactions, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 Reactogenicity Subset for Phase 2/3 Analysis \u2013 Safety Population Age Group: 16-55 Years",
        "bbox": [0.0, 280.98, 612.0, 656.97],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_37_10",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 37,
        "filename": "Protocol Devaition log_pg37.png",
        "figure_label": "Figure 10",
        "title": "Figure 10  Participants Reporting Local Reactions, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 >55 Years",
        "description": "Figure 10  Participants Reporting Local Reactions, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 >55 Years",
        "bbox": [0.0, 65.58, 612.0, 441.57],
        "extraction_info": {"method": "Manual-Portrait", "timestamp": "2026-03-05T20:55:00Z"}
    },
    # --- Landscape pages (40, 41, 58, 81-86): full page, rotated ---
    {
        "figure_id": "Protocol_Fig_40_11.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 40,
        "filename": "Protocol Devaition log_pg40.png",
        "figure_label": "Figure 11.",
        "title": "Figure 11. Participants Reporting Systemic Events, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 16-55 Years",
        "description": "Figure 11. Participants Reporting Systemic Events, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 16-55 Years",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_41_12",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 41,
        "filename": "Protocol Devaition log_pg41.png",
        "figure_label": "Figure 12",
        "title": "Figure 12 Participants Reporting Systemic Events, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 >55 Years",
        "description": "Figure 12 Participants Reporting Systemic Events, by Maximum Severity, Within 7 Days After Each Dose, by Age Group \u2013 >55 Years",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_58_13",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 58,
        "filename": "Protocol Devaition log_pg58.png",
        "figure_label": "Figure 13",
        "title": "Figure 13 Cumulative Incidence Curves for the First COVID-19 Occurrence After Dose 1 \u2013 Dose 1 All-Available Efficacy Population",
        "description": "Figure 13 Cumulative Incidence Curves for the First COVID-19 Occurrence After Dose 1 \u2013 Dose 1 All-Available Efficacy Population",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_81_A3.1.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 81,
        "filename": "Protocol Devaition log_pg81.png",
        "figure_label": "Figure A3.1.",
        "title": "Figure A3.1. Geometric Mean Concentrations and 95% CI: SARS-CoV-2 S1-binding IgG Level Assay \u2013 18-55 Years",
        "description": "Figure A3.1. Geometric Mean Concentrations and 95% CI: SARS-CoV-2 S1-binding IgG Level Assay \u2013 18-55 Years",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_82_A3.2.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 82,
        "filename": "Protocol Devaition log_pg82.png",
        "figure_label": "Figure A3.2.",
        "title": "Figure A3.2. Geometric Mean Concentrations and 95% CI: SARS-CoV-2 S1-binding IgG Level Assay \u2013 65-85 Years",
        "description": "Figure A3.2. Geometric Mean Concentrations and 95% CI: SARS-CoV-2 S1-binding IgG Level Assay \u2013 65-85 Years",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_83_A3.3.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 83,
        "filename": "Protocol Devaition log_pg83.png",
        "figure_label": "Figure A3.3.",
        "title": "Figure A3.3. Subjects Reporting Local Reactions, by Maximum Severity \u2013 18-55 Years \u2013 BNT162b2",
        "description": "Figure A3.3. Subjects Reporting Local Reactions, by Maximum Severity \u2013 18-55 Years \u2013 BNT162b2",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_84_A3.4.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 84,
        "filename": "Protocol Devaition log_pg84.png",
        "figure_label": "Figure A3.4.",
        "title": "Figure A3.4. Subjects Reporting Local Reactions, by Maximum Severity \u2013 65-85 Years \u2013 BNT162b2",
        "description": "Figure A3.4. Subjects Reporting Local Reactions, by Maximum Severity \u2013 65-85 Years \u2013 BNT162b2",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_85_A3.5.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 85,
        "filename": "Protocol Devaition log_pg85.png",
        "figure_label": "Figure A3.5.",
        "title": "Figure A3.5. Subjects Reporting Systemic Events, by Maximum Severity \u2013 18-55 Years \u2013 BNT162b2",
        "description": "Figure A3.5. Subjects Reporting Systemic Events, by Maximum Severity \u2013 18-55 Years \u2013 BNT162b2",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
    {
        "figure_id": "Protocol_Fig_86_A3.6.",
        "source_pdf": "Protocol Devaition log.pdf",
        "page_number": 86,
        "filename": "Protocol Devaition log_pg86.png",
        "figure_label": "Figure A3.6.",
        "title": "Figure A3.6. Subjects Reporting Systemic Events, by Maximum Severity \u2013 65-85 Years \u2013 BNT162b2",
        "description": "Figure A3.6. Subjects Reporting Systemic Events, by Maximum Severity \u2013 65-85 Years \u2013 BNT162b2",
        "bbox": [0.0, 61.05, 792.0, 612.0],
        "extraction_info": {"method": "Manual-Landscape-Crop", "timestamp": "2026-03-05T20:55:00Z"}
    },
]

DPI = 150
LANDSCAPE_METHODS = {"Manual-Landscape-Crop"}


def crop_and_save(page, bbox_pts, out_path: Path, method: str):
    """Crop bbox from page. Landscape pages are rendered and cropped at full size."""
    x0, y0, x1, y1 = bbox_pts
    img = page.to_image(resolution=DPI).original

    if method in LANDSCAPE_METHODS:
        # For landscape pages, pdfplumber already returns the correct orientation.
        # Just crop the specified bbox proportionally.
        sx = img.size[0] / float(page.width)
        sy = img.size[1] / float(page.height)
    else:
        sx = img.size[0] / float(page.width)
        sy = img.size[1] / float(page.height)

    box = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
    img.crop(box).save(str(out_path), format="PNG")


def process_protocol_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "Protocol Devaition log"
    out_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for entry in PROTOCOL_FIGURE_MAP:
            page = pdf.pages[entry["page_number"] - 1]
            out_path = out_dir / entry["filename"]
            method = entry["extraction_info"]["method"]
            try:
                crop_and_save(page, entry["bbox"], out_path, method)
                print(f"  Saved {entry['filename']}")
            except Exception as e:
                print(f"  ERROR saving {entry['filename']}: {e}")

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump(PROTOCOL_FIGURE_MAP, f, indent=2, ensure_ascii=False)
    print(f"  Saved figure_analysis.json ({len(PROTOCOL_FIGURE_MAP)} figures)")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\Protocol Devaition log.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_protocol_figures(p, b)
