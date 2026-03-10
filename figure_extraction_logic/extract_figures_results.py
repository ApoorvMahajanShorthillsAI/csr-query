"""
Figure Extraction: Results.pdf
Method: Manual-Pattern
- 4 figures across pages 5, 8, 9, 10 — bbox-cropped.
"""
import json
import pdfplumber
from pathlib import Path


RESULTS_FIGURE_MAP = [
    {
        "figure_id": "Results_Fig_5_1",
        "source_pdf": "Results.pdf",
        "page_number": 5,
        "filename": "Results_pg5.png",
        "figure_label": "Figure 1",
        "title": "Figure 1.  What happened in this study?",
        "description": "Figure 1.  What happened in this study?",
        "bbox": [0.0, 244.01, 612.0, 415.84],
        "extraction_info": {"method": "Manual-Pattern",
                            "timestamp": "2026-03-05T20:40:00Z"}
    },
    {
        "figure_id": "Results_Fig_8_2",
        "source_pdf": "Results.pdf",
        "page_number": 8,
        "filename": "Results_pg8.png",
        "figure_label": "Figure 2",
        "title": "Figure 2.  What happened to the antibody levels against the original strain of the COVID-19 virus after the BNT booster shot?",
        "description": "Figure 2.  What happened to the antibody levels against the original strain of the COVID-19 virus after the BNT booster shot?",
        "bbox": [0.0, 92.57, 612.0, 340.0],
        "extraction_info": {"method": "Manual-Pattern",
                            "timestamp": "2026-03-05T20:40:00Z"}
    },
    {
        "figure_id": "Results_Fig_9_3",
        "source_pdf": "Results.pdf",
        "page_number": 9,
        "filename": "Results_pg9.png",
        "figure_label": "Figure 3",
        "title": "Figure 3.  How many participants had redness, swelling, or pain at the injection site within 7 days after the BNT booster shot?",
        "description": "Figure 3.  How many participants had redness, swelling, or pain at the injection site within 7 days after the BNT booster shot?",
        "bbox": [0.0, 358.73, 612.0, 696.40],
        "extraction_info": {"method": "Manual-Pattern",
                            "timestamp": "2026-03-05T20:40:00Z"}
    },
    {
        "figure_id": "Results_Fig_10_4",
        "source_pdf": "Results.pdf",
        "page_number": 10,
        "filename": "Results_pg10.png",
        "figure_label": "Figure 4",
        "title": "Figure 4.  How many participants had fever, tiredness, headache, chills, vomiting, diarrhea, muscle pain, or joint pain within 7 days after the BNT booster shot?",
        "description": "Figure 4.  How many participants had fever, tiredness, headache, chills, vomiting, diarrhea, muscle pain, or joint pain within 7 days after the BNT booster shot?",
        "bbox": [0.0, 348.77, 612.0, 697.72],
        "extraction_info": {"method": "Manual-Pattern",
                            "timestamp": "2026-03-05T20:40:00Z"}
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


def process_results_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "Results"
    out_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for entry in RESULTS_FIGURE_MAP:
            page = pdf.pages[entry["page_number"] - 1]
            out_path = out_dir / entry["filename"]
            try:
                crop_and_save(page, entry["bbox"], out_path)
                print(f"  Saved {entry['filename']}")
            except Exception as e:
                print(f"  ERROR: {e}")

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump(RESULTS_FIGURE_MAP, f, indent=2, ensure_ascii=False)
    print(f"  Saved figure_analysis.json ({len(RESULTS_FIGURE_MAP)} figures)")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\Results.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_results_figures(p, b)
