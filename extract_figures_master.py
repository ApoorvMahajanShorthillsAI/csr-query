import os
import sys
from pathlib import Path

try:
    from figure_extraction_logic.extract_figures_ib import process_ib_figures
    from figure_extraction_logic.extract_figures_ae import process_ae_figures
    from figure_extraction_logic.extract_figures_ctp import process_ctp_figures
    from figure_extraction_logic.extract_figures_icfs import process_icfs_figures
    from figure_extraction_logic.extract_figures_protocol import process_protocol_figures
    from figure_extraction_logic.extract_figures_reports import process_reports_figures
    from figure_extraction_logic.extract_figures_results import process_results_figures
    from figure_extraction_logic.extract_figures_sap import process_sap_figures
    from figure_extraction_logic.extract_figures_approval import process_approval_figures
except ImportError as e:
    print(f"Error importing figure extraction modules: {e}")
    sys.exit(1)


def main():
    print("====================================================")
    print("MODULAR PDF FIGURE EXTRACTION COORDINATOR")
    print("====================================================\n")

    input_dir = Path("Input documents for CSR")
    output_base_dir = Path("artifacts/extracted_figures")
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # --- IB.pdf --- (30 figures, Docling-Greedy-SinglePage)
    process_ib_figures(input_dir / "IB.pdf", output_base_dir)

    # --- AE.pdf --- (no figures)
    process_ae_figures(input_dir / "AE.pdf", output_base_dir)

    # --- CTP.pdf --- (no figures)
    process_ctp_figures(input_dir / "CTP.pdf", output_base_dir)

    # --- ICFs.pdf --- (1 figure, Docling-Visual-Filtered)
    process_icfs_figures(input_dir / "ICFs.pdf", output_base_dir)

    # --- Protocol Devaition log.pdf --- (19 figures, mixed portrait/landscape)
    process_protocol_figures(input_dir / "Protocol Devaition log.pdf", output_base_dir)

    # --- Reports (lab and tech).pdf --- (12 figures, Manual-Pattern)
    process_reports_figures(input_dir / "Reports (lab and tech).pdf", output_base_dir)

    # --- Results.pdf --- (4 figures, Manual-Pattern)
    process_results_figures(input_dir / "Results.pdf", output_base_dir)

    # --- SAP.pdf --- (1 figure, Manual-Pattern)
    process_sap_figures(input_dir / "SAP.pdf", output_base_dir)

    # --- Approval letter Latest.pdf --- (no figures)
    process_approval_figures(input_dir / "Approval letter Latest.pdf", output_base_dir)

    print("\n====================================================")
    print("FIGURE COORDINATOR RUN COMPLETED!")
    print("====================================================")


if __name__ == "__main__":
    main()
