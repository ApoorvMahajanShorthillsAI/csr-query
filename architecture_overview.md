# CSR Multimodal AI Agent: System Architecture & Operational Guide

This document provides a technical blueprint of the CSR AI Agent. It is designed to be passed to other AI models to explain **what** the system is and **how** it accomplishes multimodal clinical reasoning.

## 1. System Objective
The system is a "RAG+" (Retrieval-Augmented Generation with Multimodal capabilities) pipeline. It transforms unstructured Pfizer-BioNTech COVID-19 Clinical Study Reports (CSR) into a structured, searchable knowledge base that an LLM can query using text, data tables, and visual charts.

## 2. Component Architecture

### A. Extraction Layer (Offline/Preprocessing)
*   **Modules**: `extract_tables_master.py`, `extract_figures_master.py`.
*   **Logic**:
    *   **Tables**: Uses `pdfplumber` (grid detection) and `camelot` (stream mode) to extract tables into GitHub-Flavored Markdown (`.md`).
    *   **Figures**: Crops images from PDFs based on bounding boxes, saving them as `.png` files.
*   **Metadata**: Each extraction generates a `.json` file containing the source PDF, page number, caption, and coordinates.

### B. Ingestion Layer (`ingestion.py`)
*   **Function**: `load_all_assets()`.
*   **Process**:
    1.  Scans the `artifacts/` directory.
    2.  Loads Markdown tables into memory.
    3.  Loads Figure metadata and caches file paths.
    4.  Extracts raw text from all PDFs and splits them into **semantic chunks** (sentences/paragraphs).

### C. Retrieval Engine (`retrieval.py`)
*   **Function**: `retrieve()`.
*   **Mechanism**:
    1.  Uses `TfidfVectorizer` from `scikit-learn` to vectorize the User Query.
    2.  Calculates **Cosine Similarity** between the query vector and the vectors of all text chunks, table captions/content, and figure captions.
    3.  Returns the **Top-K** most relevant items (Text, Tables, and Figures) for the specific query.

### D. AI Agent Core (`query_agent.py`)
*   **Function**: `answer()`.
*   **Orchestration**:
    1.  **Context Assembly**: Combines the retrieved context into a multimodal prompt.
    2.  **Multimodal Handling**: 
        *   **Tables** are injected as raw Markdown strings.
        *   **Figures** are loaded from disk, base64-encoded, and passed as `PIL.Image` objects (native vision parts).
    3.  **LLM Call**: Sends the structured multimodal payload to **Gemini 2.5 Pro** via the `google-generativeai` SDK.

## 3. Data Flow Pipeline
1.  **Input**: User asks a clinical question (e.g., "What was the IgG GMC in the 30µg group?").
2.  **Retrieval**: The engine finds 5 text chunks, 3 relevant tables (Markdown), and 2 relevant figures (PNGs).
3.  **Prompting**: The agent builds a system prompt instructing the model to act as a clinical expert.
4.  **Multimodal Inference**: Gemini processes the text/tables and "looks" at the figures simultaneously to formulate an answer.
5.  **Output**: A structured expert response with citations for every source (PDF + Page).

## 4. Technical Stack
| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.10+ |
| **LLM / Vision** | Google Gemini 2.5 Pro |
| **SDK** | `google-generativeai` |
| **Retrieval** | `scikit-learn` (TF-IDF) |
| **PDF Parsing** | `pdfplumber`, `camelot-py` |
| **PDF Reporting** | `fpdf2`, `markdown2` |
| **Image Processing** | `Pillow` |

## 5. Instructions for AI Models Interacting with this System
*   **Grounding**: Always verify numbers in the generated answer against the Markdown table content provided in the context.
*   **Visual Logic**: When a figure is provided, analyze the trend lines and axis labels in the PNG to confirm textual claims.
*   **Citations**: The system relies on the `source_pdf` and `page_number` keys in the asset metadata for strict clinical traceability.
