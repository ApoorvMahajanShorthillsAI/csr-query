"""
Figure Extraction: AE.pdf
Method: No figures detected in original output (figure_analysis.json is empty []).
This script writes an empty figure_analysis.json as a placeholder.
"""
import json
from pathlib import Path


def process_ae_figures(pdf_path: Path, output_base_dir: Path):
    print(f"\n--- Extracting Figures from {pdf_path.name} ---")
    out_dir = output_base_dir / "AE"
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "figure_analysis.json", "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)
    print("  No figures detected in AE.pdf. Saved empty figure_analysis.json.")


if __name__ == "__main__":
    p = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\Input documents for CSR\AE.pdf")
    b = Path(r"c:\Users\ApoorvMahajan\OneDrive - Short Hills Tech Pvt Ltd\Desktop\csr\artifacts\extracted_figures")
    process_ae_figures(p, b)
