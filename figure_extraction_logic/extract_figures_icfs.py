"""
Figure Extraction: ICFs.pdf
Method: Docling-Visual-Filtered
- One unnumbered figure (Coronavirus image) at page 5, bbox-cropped.
"""
import json
import pdfplumber
from pathlib import Path


ICF_FIGURE_MAP = [
    {
        "figure_id": "ICFs_Fig_5_1",
        "source_pdf": "ICFs.pdf",
        "page_number": 5,
        "filename": "ICFs_pg5.png",
        "figure_label": "Unnumbered Figure",
        "title": "Coronavirus image",
        "description": "Coronavirus image found in ICFs.pdf (no standard figure format)",
        "bbox": [225.8, 425.1, 396.0, 497.2],
        "extraction_info": {"method": "Docling-Visual-Filtered",
                            "timestamp": "2026-03-05T20:50:00Z"}
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


def process_icfs_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "ICFs"
    out_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for entry in ICF_FIGURE_MAP:
            page = pdf.pages[entry["page_number"] - 1]
            out_path = out_dir / entry["filename"]
            try:
                crop_and_save(page, entry["bbox"], out_path)
                print(f"  Saved {entry['filename']}")
            except Exception as e:
                print(f"  ERROR: {e}")

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump(ICF_FIGURE_MAP, f, indent=2, ensure_ascii=False)
    print(f"  Saved figure_analysis.json ({len(ICF_FIGURE_MAP)} figures)")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\ICFs.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_icfs_figures(p, b)
