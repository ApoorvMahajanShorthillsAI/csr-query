# CSR PDF Extraction & AI Query Pipeline: Technical Documentation

# PART 1: Figure / Image Extraction

## Overview
This component of the pipeline is responsible for precisely extracting visual assets (charts, graphs, clinical diagrams) from clinical study reports. These figures are essential for "visual RAG," allowing the AI agent to interpret data that is lost in standard text extraction, such as dose-response curves and safety trend charts.

- **Objective**: Identify, crop, and categorize all visual clinical data.
- **Source PDFs with Figures**: IB, ICFs, Protocol, Reports, Results, SAP.
- **Source PDFs without Figures**: AE, CTP, Approval (contain exclusively text/tables).
- **Total Figure Count**: 67 figures extracted across the corpus.

## Technical Approach
The extraction uses a "render-and-crop" methodology to ensure maximum visual fidelity.

- **Libraries**: `pdfplumber` for high-quality page rendering and bounding box handling; `Pillow` (PIL) for image cropping and optimization.
- **Resolution**: Rendered at **150 DPI**. This provides a balance between image clarity for OCR/Vision models and file size efficiency.
- **Coordinate System**: Bounding boxes (bbox) are defined as `[x0, y0, x1, y1]` in standard PDF points (1/72 inch). The origin `(0,0)` is the **top-left** of the page.
- **Coordinate Derivation**: Bbox values were derived through a hybrid of automated detection and manual verification to ensure no legends or axis labels were cut off.
- **Scaling Formula**: Since PDF points differ from image pixels, the code calculates current scale factors:
  ```python
  sx = img_pixel_width / page_point_width
  sy = img_pixel_height / page_point_height
  # Final crop box
  pixel_box = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
  ```

## Extraction Methods
| Method Name | Description | When Used | Example PDF |
| :--- | :--- | :--- | :--- |
| **Docling-Greedy-SinglePage** | Automated detection of all figure-like elements on a page. | When figures occupy dedicated pages or clear regions. | `IB.pdf` |
| **Docling-Visual-Filtered** | Extraction with vision-based noise filtering. | When figures are surrounded by complex text or headers. | `ICFs.pdf` |
| **Manual-Pattern** | Coordinate-based extraction from known fixed layouts. | High-precision extraction from structured report pages. | `Results.pdf` |
| **Manual-Portrait** | Full-page crop for portrait orientation charts. | Standard report figures. | `Protocol.pdf` |
| **Manual-Portrait-Stitched**| Merging multiple vertical regions into one image. | Figures with split legends/sub-charts. | `Protocol.pdf` |
| **Manual-Landscape-Crop** | Extraction from landscape-oriented pages. | Broad statistical charts and timelines. | `Protocol.pdf` |

## Output Format
- **Naming Convention**: `{PDF_STEM}_Fig_{N}_pg{PAGE}.png` (e.g., `IB_Fig_1_pg13.png`)
- **Structure**: All figures are organized by source PDF subfolders under `artifacts/extracted_figures/`.
- **Metadata**: Each folder contains a `figure_analysis.json` file.

**Analysis JSON Schema Example**:
```json
{
  "figure_id": "IB_Fig_1",
  "source_pdf": "IB.pdf",
  "page_number": 13,
  "filename": "IB_Fig_1_pg13.png",
  "figure_label": "Figure 1:",
  "title": "Figure 1: Overview of the three RNA platforms",
  "bbox": [70.92, 411.14, 375.43, 643.44],
  "extraction_info": { "method": "Docling-Greedy-SinglePage" }
}
```

## Per-PDF Summary Table
| PDF | Figure Count | Special Handling Notes |
| :--- | :--- | :--- |
| **IB.pdf** | 30 | High-yield immunogenicity and reactogenicity charts. |
| **ICFs.pdf** | 1 | Simple flowchart extraction using Docling-Visual. |
| **Protocol.pdf** | 19 | Mixed portrait/landscape; several stitched figures. |
| **Reports.pdf** | 12 | Complex antibody neutralization curves (VN50/NT50). |
| **Results.pdf** | 4 | "Plain language" results summary charts. |
| **SAP.pdf** | 1 | Statistical multiplicity schema figure. |
| **Others** | 0 | AE, CTP, and Approval contain no usable visual figures. |

## How to Run
To regenerate all visual assets:
```bash
python extract_figures_master.py
```
This master script orchestrates specialized logic for each PDF found in `figure_extraction_logic/`.

---

# PART 2: Table Extraction

## Overview
This layer converts dense clinical tables into LLM-readable Markdown. Clinical PDFs often use complex cell merging or borderless layouts that traditional parsers fail on.

- **Objective**: Robust extraction of clinical data with structural integrity.
- **Total Table Count**: 149 tables.
- **Format Choice**: **GitHub-Flavored Markdown (GFM)**. This format is natively understood by LLMs like Gemini and preserves column relationships better than raw text.

## Technical Approach
The pipeline uses a tiered strategy based on the PDF's internal structure:

- **Primary**: `pdfplumber` for grid-based tables using `page.extract_tables()`. This is highly reliable for Pfizer's standard report tables.
- **Fallback**: "Word Bounding Box" logic using `page.extract_words()`. This groups words by Y-coordinates (lines) and X-coordinates (columns) to Reconstruct tables that lack visible borders.
- **Specialized**: `camelot` (Stream mode) is used for the `AE.pdf` publication, which uses a non-standard 2-column academic layout.
- **Stitching**: For tables spanning multiple pages (e.g., SAP Table 3), the code looks for header repetition and vertical proximity to merge `pandas` DataFrames before exporting to Markdown.

## Per-PDF Extraction Details
| PDF | Table Count | Strategy Used | Special Handling |
| :--- | :--- | :--- | :--- |
| **IB** | 19 | Dual (Grid + Text Parsing) | Handles text-based inline nomenclature tables. |
| **AE** | 4 | Camelot Stream | Optimized for academic publication layouts. |
| **CTP** | 41 | Multi-page Grid | Stitches 5+ page Schedule of Activities tables. |
| **ICFs** | 12 | Full Page Scan | Captures structured consent forms. |
| **Protocol** | 38 | Multi-page Merge | Handles redacted content (represented as `null`). |
| **Reports** | 20 | Hybrid (Grid + Word Bbox) | Page 102 tables (15/16) are images (headers only). |
| **Results**| 1 | Targeted Grid | Precision extraction of page 13 summary. |
| **SAP** | 13 | Multi-page / Stat-Logic | Merged Table 3 (7 pages); probability stat tables. |
| **Approval**| 1 | Regex / Narrative | Extracts PMC schedules from free-form text. |

## Output Format
- **Naming Convention**: `Table_{N}.md` (e.g., `Table_1.md`)
- **Structure**: Located in `artifacts/extracted_tables/{PDF_NAME}/`.
- **Metadata JSON Schema**:
```json
{
    "TableNumber": 1,
    "Title": "Characteristics of candidates...",
    "Pages": "18",
    "Section": "3.4 Clinical development",
    "ColumnCount": 4,
    "RowCount": 6,
    "Description": "Overview of RNA platforms used."
}
```

## Edge Cases Documented
- **Redaction**: In the Protocol Deviation Log, redacted cells are detected as empty/garbage and converted to `null` or `[Redacted]` in Markdown.
- **Image-Based Tables**: In the Lab/Tech Reports (Tables 15/16), the tables are embedded as images. The script captures the text header/description but provides a placeholder for the content.
- **Narrative Extraction**: The FDA Approval letter tables are not real grids; they are extracted using regex patterns to find "PMC #1", "PMC #2", etc., and structured into a Markdown schedule.

## How to Run
To regenerate all table assets:
```bash
python extract_tables_master.py
```

---

# PART 3: AI Query Agent (RAG+ Pipeline)

## System Overview
The architecture is a **Multimodal RAG+** system. It goes beyond text-only Retrieval-Augmented Generation by treating Markdown tables and Base64 images as first-class citizens in the retrieval and reasoning process.

- **Core Value**: By pre-extracting tables and figures, we avoid the "hallucination" and structural loss common when LLMs try to parse raw PDF streams on the fly.

## Architecture
| Component | File | Technology | Purpose |
| :--- | :--- | :--- | :--- |
| **Ingestion** | `ingestion.py` | `pdfplumber`, `PIL`, `json` | Parallel loading of Markdown, base64 images, and text. |
| **Retrieval** | `retrieval.py` | `scikit-learn` (TF-IDF) | Content-aware semantic retrieval of top-K assets. |
| **Agent Core** | `query_agent.py` | `google-generativeai` | Prompt orchestration for Gemini 2.5 Pro. |
| **Demo Runner**| `demo.py` | Python standard libs | Pre-configured clinical expert query suite. |

## Ingestion Layer
The `load_all_assets()` function builds a unified memory map of the corpus.
- **Return Schema**:
```python
{
    "tables": [...],      # Path, Markdown content, metadata
    "figures": [...],     # Path, Base64 data, id, caption
    "text_chunks": [...]  # Normalized text per PDF page
}
```
- **Search Blobs**: Each asset generates a `_search_blob`—a concatenated string of its PDF source, title, section, and first 500 characters—used for vectorization.

## Retrieval Engine
- **Approach**: Uses TF-IDF vectorization with `ngram_range=(1, 2)` to capture clinical technical terms (e.g., "dose group", "adverse event").
- **Scoring**: Cosine similarity is used to rank query-to-asset relevance.
- **Top-K Strategy**: 
    - Text: Top 5 pages
    - Tables: Top 3 Markdown files
    - Figures: Top 3 Figure PNGs (based on caption/id similarity)

## AI Agent Core
The agent orchestrates the **Multimodal Prompt** sent to **Gemini 2.5 Pro**.

### Prompt Assembly Order
1.  **System Prompt**: Defines the persona (Senior Clinical Expert).
2.  **Narrative Context**: Relevant raw text excerpts for general context.
3.  **Data Context**: Markdown tables injected directly into the message.
4.  **Visual Context**: Figures passed as native `PIL.Image` objects (vision tokens).

### LLM Execution
The agent uses the the `GEMINI_API_KEY` for authentication and calls `model.generate_content()` with the multi-part data list.

## Sample Queries
The system is validated against 5 expert clinical patterns:
1.  **Safety & Frequencies**: "What were the most frequent adverse events?" (Retrieves AE/Protocol tables).
2.  **Methodology**: "Show the statistical analysis plan." (Retrieves SAP tables/text).
3.  **Visualization**: "Show me the neutralization graphs for BNT162b2." (Retrieves Reports/IB figure PNGs).
4.  **Compliance**: "Summarize protocol deviations by site." (Retrieves Deviation Log tables).
5.  **Clinical Outcomes**: "What were the key results for elderly populations?" (Retrieves Results and IB context).

## Response Output Schema
Successful queries return a JSON object:
```json
{
  "query": "The user's question",
  "answer": "Expert clinical reasoning + markdown tables/figures explanation",
  "sources_cited": [ {"pdf": "IB", "page": 57}, ... ],
  "tables_used": [ {"table_id": "Table_1", "caption": "...", "file_path": "..."} ],
  "figures_used": [ {"figure_id": "IB_Fig_1", "caption": "...", "file_path": "..."} ]
}
```

## How to Run
Set your API key and execute the expert suite:
```powershell
# Windows
set GEMINI_API_KEY=AIza...
python demo.py
```

## Dependencies
Extracted from `requirements.txt`:
- `pdfplumber` (PDF parsing)
- `google-generativeai` (Gemini SDK)
- `scikit-learn` (Retrieval)
- `pandas` & `tabulate` (Markdown tables)
- `Pillow` (Images)
- `camelot-py[cv]` (Stream tables)
- `numpy` (Numerical ops)
