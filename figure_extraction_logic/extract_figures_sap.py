"""
Figure Extraction: SAP.pdf
Method: Manual-Pattern
- One figure (Multiplicity Schema) at page 48, bbox-cropped.
"""
import json
import pdfplumber
from pathlib import Path


SAP_FIGURE_MAP = [
    {
        "figure_id": "SAP_Fig_48_1",
        "source_pdf": "SAP.pdf",
        "page_number": 48,
        "filename": "SAP_pg48.png",
        "figure_label": "Figure 1",
        "title": "Figure 1.Multiplicity Schema",
        "description": "Figure 1.Multiplicity Schema",
        "bbox": [0.0, 67.47, 612.0, 305.92],
        "extraction_info": {"method": "Manual-Pattern",
                            "timestamp": "2026-03-05T20:45:00Z"}
    }
]

DPI = 150


def crop_and_save(page, bbox_pts, out_path: Path):
    x0, y0, x1, y1 = bbox_pts
    img = page.to_image(resolution=DPI).original
    sx = img.size[0] / float(page.width)
    sy = img.size[1] / float(page.height)
    box = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
    img.crop(box).save(str(out_path), format="PNG")


def process_sap_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "SAP"
    out_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for entry in SAP_FIGURE_MAP:
            page = pdf.pages[entry["page_number"] - 1]
            out_path = out_dir / entry["filename"]
            try:
                crop_and_save(page, entry["bbox"], out_path)
                print(f"  Saved {entry['filename']}")
            except Exception as e:
                print(f"  ERROR: {e}")

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump(SAP_FIGURE_MAP, f, indent=2, ensure_ascii=False)
    print(f"  Saved figure_analysis.json ({len(SAP_FIGURE_MAP)} figures)")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\SAP.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_sap_figures(p, b)
