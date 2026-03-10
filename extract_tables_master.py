import os
import sys
from pathlib import Path

# Placeholder imports for modular table extraction
try:
    from table_extraction_logic.extract_tables_ib import process_ib_tables
    from table_extraction_logic.extract_tables_reports import process_reports_tables
    from table_extraction_logic.extract_tables_results import process_results_tables
    from table_extraction_logic.extract_tables_sap import process_sap_tables
    from table_extraction_logic.extract_tables_icfs import process_icfs_tables
    from table_extraction_logic.extract_tables_protocol import process_protocol_tables
    from table_extraction_logic.extract_tables_ae import process_ae_tables
    from table_extraction_logic.extract_tables_approval import process_approval_tables
    from table_extraction_logic.extract_tables_ctp import process_ctp_tables
except ImportError as e:
    print(f"Error importing table extraction modules: {e}")
    # In a real run, we'd handle this, but for now it's just scaffolding.

def main():
    print("====================================================")
    print("MODULAR PDF TABLE EXTRACTION COORDINATOR")
    print("====================================================\n")

    input_dir = Path("Input documents for CSR")
    output_base_dir = Path("artifacts/extracted_tables")
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Modular table extraction calls (Currently placeholders)
    
    # --- IB.pdf ---
    process_ib_tables(input_dir / "IB.pdf", output_base_dir)

    # --- Reports (lab and tech).pdf ---
    process_reports_tables(input_dir / "Reports (lab and tech).pdf", output_base_dir)

    # --- Results.pdf ---
    process_results_tables(input_dir / "Results.pdf", output_base_dir)

    # --- SAP.pdf ---
    process_sap_tables(input_dir / "SAP.pdf", output_base_dir)

    # --- ICFs.pdf ---
    process_icfs_tables(input_dir / "ICFs.pdf", output_base_dir)

    # --- Protocol Devaition log.pdf ---
    process_protocol_tables(input_dir / "Protocol Devaition log.pdf", output_base_dir)

    # --- AE.pdf ---
    process_ae_tables(input_dir / "AE.pdf", output_base_dir)

    # --- Approval letter Latest.pdf ---
    process_approval_tables(input_dir / "Approval letter Latest.pdf", output_base_dir)

    # --- CTP.pdf ---
    process_ctp_tables(input_dir / "CTP.pdf", output_base_dir)

    print("\n====================================================")
    print("TABLE COORDINATOR RUN COMPLETED!")
    print("====================================================")

if __name__ == "__main__":
    main()
