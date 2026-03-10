"""
ingestion.py — Loads ALL extracted assets (tables, figures, PDF text) into memory.

Exposes:
    load_all_assets(base_dir: str) -> dict
        Returns {"tables": [...], "figures": [...], "text_chunks": [...]}
"""

import os
import json
import base64
import logging
import warnings
from pathlib import Path

import pdfplumber

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="[ingestion] %(message)s")
logger = logging.getLogger(__name__)

# ── PDF display name → actual filename stem mapping ──────────────────────────
# Keys must match the subfolder names under extracted_tables/ and extracted_figures/
PDF_FOLDER_TO_FILE = {
    "IB": "IB.pdf",
    "AE": "AE.pdf",
    "CTP": "CTP.pdf",
    "ICFs": "ICFs.pdf",
    "Protocol": "Protocol Devaition log.pdf",
    "Reports": "Reports (lab and tech).pdf",
    "Results": "Results.pdf",
    "SAP": "SAP.pdf",
    "Approval": "Approval letter Latest.pdf",
}

# Figure subfolder names (may differ from table subfolder names)
FIGURE_FOLDER_TO_PDF = {
    "IB": "IB",
    "AE": "AE",
    "CTP": "CTP",
    "ICFs": "ICFs",
    "Protocol Devaition log": "Protocol",
    "Reports (lab and tech)": "Reports",
    "Results": "Results",
    "SAP": "SAP",
    "Approval letter Latest": "Approval",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_page_from_pages_field(pages_str):
    """Parse first page number from a string like '18', '21-22', '4-5'."""
    if not pages_str:
        return None
    try:
        return int(str(pages_str).split("-")[0].strip())
    except (ValueError, AttributeError):
        return None


def _load_metadata_json(path: Path):
    """Load a metadata JSON file, returning [] on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read metadata JSON {path}: {e}")
        return []


def _encode_image(path: Path) -> str:
    """Base64-encode a PNG file."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Table loading ─────────────────────────────────────────────────────────────

def _load_tables(tables_root: Path) -> list:
    records = []

    for subfolder in sorted(tables_root.iterdir()):
        if not subfolder.is_dir():
            continue
        source_pdf = subfolder.name  # e.g. "IB", "AE", "Approval"

        # Load metadata JSON (may be named *_tables_metadata.json)
        meta_files = list(subfolder.glob("*_tables_metadata.json"))
        meta_lookup = {}  # TableNumber (int) -> metadata dict
        if meta_files:
            meta_list = _load_metadata_json(meta_files[0])
            for item in meta_list:
                try:
                    num = int(item.get("TableNumber", 0))
                    meta_lookup[num] = item
                except (ValueError, TypeError):
                    pass
        else:
            logger.warning(f"No metadata JSON found in {subfolder}")

        # Load each .md file
        md_files = sorted(subfolder.glob("*.md"))
        for md_path in md_files:
            try:
                content = md_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                logger.warning(f"Cannot read {md_path}: {e}")
                continue

            # Try to parse table number from filename, e.g. Table_1.md → 1
            stem = md_path.stem  # "Table_1" or "PMC_Schedules"
            table_num = None
            if stem.startswith("Table_"):
                try:
                    table_num = int(stem.split("_")[1])
                except (IndexError, ValueError):
                    pass

            meta = meta_lookup.get(table_num, {})
            page_raw = meta.get("Pages", None)
            page_number = _parse_page_from_pages_field(page_raw)

            caption = meta.get("Title", stem.replace("_", " "))
            description = meta.get("Description", "")
            section = meta.get("Section", "")

            # Searchable text blob
            search_blob = " ".join(filter(None, [
                source_pdf, caption, description, section, content[:500]
            ]))

            records.append({
                "type": "table",
                "source_pdf": source_pdf,
                "table_id": stem,
                "page_number": page_number,
                "caption": caption,
                "description": description,
                "section": section,
                "content": content,
                "file_path": str(md_path.resolve()),
                "_search_blob": search_blob,
            })

    logger.info(f"Loaded {len(records)} table records")
    return records


# ── Figure loading ─────────────────────────────────────────────────────────────

def _load_figures(figures_root: Path) -> list:
    records = []

    for subfolder in sorted(figures_root.iterdir()):
        if not subfolder.is_dir():
            continue

        folder_name = subfolder.name  # e.g. "IB", "Protocol Devaition log"
        source_pdf = FIGURE_FOLDER_TO_PDF.get(folder_name, folder_name)

        # Load figure_analysis.json
        meta_path = subfolder / "figure_analysis.json"
        meta_list = _load_metadata_json(meta_path) if meta_path.exists() else []
        # Build lookup: filename → metadata
        meta_by_filename = {}
        for item in meta_list:
            fn = item.get("filename", "")
            if fn:
                meta_by_filename[fn] = item

        png_files = sorted(subfolder.glob("*.png"))
        if not png_files:
            logger.info(f"No PNG files in {subfolder} (expected for AE/CTP/Approval)")
            continue

        for png_path in png_files:
            meta = meta_by_filename.get(png_path.name, {})

            # Parse page from filename fallback: *_pg18.png or *_pg23.png
            page_number = meta.get("page_number", None)
            if page_number is None:
                stem = png_path.stem  # e.g. "IB_Fig_1_pg13"
                parts = stem.rsplit("_pg", 1)
                if len(parts) == 2:
                    try:
                        page_number = int(parts[1].split("_")[0])
                    except ValueError:
                        pass

            figure_id = meta.get("figure_id", png_path.stem)
            caption = meta.get("title", meta.get("figure_label", png_path.stem))
            description = meta.get("description", "")
            method = meta.get("extraction_info", {}).get("method", "Unknown")

            try:
                b64 = _encode_image(png_path)
            except Exception as e:
                logger.warning(f"Cannot encode {png_path}: {e}")
                continue

            search_blob = " ".join(filter(None, [
                source_pdf, figure_id, caption, description
            ]))

            records.append({
                "type": "figure",
                "source_pdf": source_pdf,
                "figure_id": figure_id,
                "page_number": page_number,
                "caption": caption,
                "description": description,
                "method": method,
                "base64": b64,
                "file_path": str(png_path.resolve()),
                "_search_blob": search_blob,
            })

    logger.info(f"Loaded {len(records)} figure records")
    return records


# ── PDF text loading ────────────────────────────────────────────────────────

def _load_text_chunks(pdf_input_dir: Path, table_folder_to_pdf: dict) -> list:
    records = []

    for folder_name, pdf_filename in table_folder_to_pdf.items():
        pdf_path = pdf_input_dir / pdf_filename
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            continue

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    text = text.strip()
                    if not text:
                        continue
                    records.append({
                        "type": "text",
                        "source_pdf": folder_name,
                        "page_number": page_num,
                        "content": text,
                        "_search_blob": f"{folder_name} page {page_num} {text[:800]}",
                    })
            logger.info(f"  Chunked {pdf_filename}: {page_num} pages")
        except Exception as e:
            logger.warning(f"Cannot open {pdf_path}: {e}")

    logger.info(f"Loaded {len(records)} text chunk records")
    return records


# ── Public API ────────────────────────────────────────────────────────────────

def load_all_assets(base_dir: str) -> dict:
    """
    Load all extracted assets from the csr/ project directory.

    Args:
        base_dir: Absolute or relative path to the csr/ root directory.

    Returns:
        {
            "tables":      [...],   # table records
            "figures":     [...],   # figure records
            "text_chunks": [...],   # per-page text records
        }
    """
    base = Path(base_dir).resolve()
    tables_root = base / "artifacts" / "extracted_tables"
    figures_root = base / "artifacts" / "extracted_figures"
    pdf_input_dir = base / "Input documents for CSR"

    logger.info(f"Loading assets from: {base}")

    tables = _load_tables(tables_root)
    figures = _load_figures(figures_root)
    text_chunks = _load_text_chunks(pdf_input_dir, PDF_FOLDER_TO_FILE)

    return {
        "tables": tables,
        "figures": figures,
        "text_chunks": text_chunks,
    }


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    assets = load_all_assets(base)
    print(f"\nSummary:")
    print(f"  Tables:      {len(assets['tables'])}")
    print(f"  Figures:     {len(assets['figures'])}")
    print(f"  Text chunks: {len(assets['text_chunks'])}")
