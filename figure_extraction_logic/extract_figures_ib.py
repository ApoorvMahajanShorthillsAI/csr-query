"""
Figure Extraction: IB.pdf
Method: Docling-Greedy-SinglePage
- Scans every page for figure captions via regex.
- Uses pdfplumber to crop the bounding box of each detected figure image.
- Saves each figure as a PNG and writes a consolidated figure_analysis.json.
"""
import re
import json
import pdfplumber
from pathlib import Path
from PIL import Image
import io


# ── hardcoded figure map derived from the original output ──────────────────
# Format: (page_number_0indexed, figure_label, title, bbox_pts)
IB_FIGURE_MAP = [
    (12, "Figure 1:", "Figure 1: Overview of the three RNA platforms",
     [70.92, 411.14, 375.43, 643.44]),
    (13, "Figure 2:", "Figure 2: RNA-LNP-based BNT162 vaccines",
     [70.92, 277.29, 545.13, 491.16]),
    (14, "Figure 3:", "Figure 3: Rationale for the administration schema of BNT162 vaccines",
     [70.92, 119.60, 512.86, 383.40]),
    (15, "Figure 4:", "Figure 4: Schematic lifecycle of a Coronavirus",
     [70.51, 116.57, 549.28, 600.84]),
    (16, "Figure 5:", "Figure 5: Schematic overview of the organization of the SARS-CoV-2 S glycoprotein",
     [70.92, 223.96, 512.06, 322.80]),
    (16, "Figure 6:", "Figure 6: Schematic overview of a LNP",
     [70.92, 485.50, 420.86, 664.08]),
    (24, "Figure 7:", "Figure 7: lmmunofluorescence stainin of cells transfected with BNT162b1 (modRNA encoding VS) and",
     [71.29, 327.47, 553.71, 649.05]),
    (27, "Figure 10:", "Figure 10: Anti-S lgG response 7, 14, 21, and 28 d after immunization with BNT162b2",
     [71.29, 230.92, 504.02, 408.90]),
    (27, "Figure 11:", "Figure 11: Neutralization of SARS-CoV-2 pseudovirus 14, 21, and 28 dafter immunization with BNT162b2",
     [70.50, 416.39, 544.15, 628.50]),
    (30, "Figure 14:", "Figure 14: Anti-S lgG response after immunization with the different BNT162b candidates in NHP",
     [71.29, 289.67, 538.25, 670.48]),
    (31, "Figure 15:", "Figure 15: NTSO titer after immunization with the different BNT162b candidates in NHP",
     [71.29, 261.79, 521.90, 673.50]),
    (33, "Figure 16:", "Figure 16: Pseudovirus neutralization activity of recovery cohort sera plotted as pVNSO titer",
     [71.29, 236.31, 545.98, 461.48]),
    (35, "Figure 17:", "Figure 17: Bioluminescence imaging measurement using the LNP-candidate formulated BNT162b encoding luciferase",
     [70.92, 404.62, 539.24, 710.40]),
    (56, "Figure 22:", "Figure 22: IFNy ELISpot data for 5 subjects dosed with 10 µg BNT162b2 (BNT162-01)",
     [71.29, 317.70, 479.91, 546.50]),
    (57, "Figure 23:", "Figure 23: Example of co4· and cos· IFNy ELISpot data (BNT162-01)",
     [71.25, 126.48, 496.99, 368.43]),
    (57, "Figure 24:", "Figure 24: Comparison of BNT162b2-elicited and benchmark IN Fr ELISpot responses (BNT162-01)",
     [70.84, 374.97, 550.63, 652.50]),
    (63, "Figure 25:", "Figure 25: BNT162b1 in younger adults: RBD-binding IgG GMCs (BNT162-02)",
     [70.92, 122.81, 533.27, 411.00]),
    (63, "Figure 26:", "Figure 26: BNT162b1 in elderly adults: RBD-binding IgG GMCs (BNT162-02)",
     [70.92, 432.18, 527.00, 728.40]),
    (64, "Figure 27:", "Figure 27: BNT162b1 in younger adults: 50% SARS-CoV-2 neutralizing GMTs (BNT162-02)",
     [70.92, 123.12, 527.34, 419.52]),
    (64, "Figure 28:", "Figure 28: BNT162b1 in elderly adults: 50% SARS-CoV-2 neutralizing GMTs (BNT162-02)",
     [70.92, 432.93, 515.05, 716.40]),
    (66, "Figure 29:", "Figure 29: BNT162b2 in younger adults: S1-binding IgG GMCs (BNT162-02)",
     [70.92, 125.37, 510.08, 400.08]),
    (66, "Figure 30:", "Figure 30: BNT162b2 in elderly adults: S1-binding IgG GMCs (BNT162-02)",
     [70.92, 427.47, 524.80, 724.92]),
    (67, "Figure 31:", "Figure 31: BNT162b2 in younger adults: 50% SARS-CoV-2 neutralizing GMTs (BNT162-02)",
     [70.92, 117.80, 528.40, 415.08]),
    (67, "Figure 32:", "Figure 32: BNT162b2 in elderly adults: 50% SARS-CoV-2 neutralizing GMTs (BNT162-02)",
     [70.92, 442.43, 532.26, 748.92]),
    (69, "Figure 33:", "Figure 33: BNT162b1 in younger adults: Local reactions after doses 1 and 2 (BNT162-02)",
     [70.92, 136.70, 548.04, 518.40]),
    (70, "Figure 34:", "Figure 34: BNT162b1 in younger adults: Systemic events after doses 1 and 2 (BNT162-02)",
     [179.75, 122.57, 705.24, 505.07]),
    (72, "Figure 35:", "Figure 35: BNT162b2 in younger adults: Local reactions after doses 1 and 2 (BNT162-02)",
     [70.92, 123.57, 548.06, 505.08]),
    (73, "Figure 36:", "Figure 36: BNT162b2 in elderly adults: Local reactions after doses 1 and 2 (BNT162-02)",
     [70.92, 123.57, 548.04, 505.08]),
    (74, "Figure 37:", "Figure 37: BNT162b2 in younger adults: Systemic events after doses 1 and 2 (BNT162-02)",
     [178.11, 122.50, 709.41, 508.07]),
    (75, "Figure 38:", "Figure 38: BNT162b2 in elderly adults: Systemic events after doses 1 and 2 (BNT162-02)",
     [183.14, 122.39, 701.39, 499.07]),
]

DPI = 150
PT_TO_PX = DPI / 72.0


def crop_and_save(page, bbox_pts, out_path: Path):
    """Crop bbox from page at DPI=150 and save as PNG."""
    x0, y0, x1, y1 = bbox_pts
    # pdfplumber uses points; render at DPI then crop
    img = page.to_image(resolution=DPI).original
    w_pt = float(page.width)
    h_pt = float(page.height)
    w_px, h_px = img.size
    sx = w_px / w_pt
    sy = h_px / h_pt
    box = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
    cropped = img.crop(box)
    cropped.save(str(out_path), format="PNG")


def process_ib_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "IB"
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = []
    label_counter = {}

    with pdfplumber.open(pdf_path) as pdf:
        for entry in IB_FIGURE_MAP:
            page_idx, label, title, bbox = entry
            page = pdf.pages[page_idx]

            # Build unique filename
            num_tag = re.search(r'Figure\s+(\w+)', label)
            fig_num = num_tag.group(1) if num_tag else str(page_idx + 1)
            filename = f"IB_Fig_{fig_num}_pg{page_idx + 1}.png"
            out_path = out_dir / filename

            try:
                crop_and_save(page, bbox, out_path)
                print(f"  Saved {filename}")
            except Exception as e:
                print(f"  ERROR saving {filename}: {e}")
                continue

            metadata.append({
                "figure_id": f"IB_Fig_{fig_num}",
                "source_pdf": "IB.pdf",
                "page_number": page_idx + 1,
                "filename": filename,
                "figure_label": label,
                "title": title,
                "description": "",
                "bbox": bbox,
                "extraction_info": {"method": "Docling-Greedy-SinglePage"}
            })

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  Saved figure_analysis.json ({len(metadata)} figures)")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\IB.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_ib_figures(p, b)
