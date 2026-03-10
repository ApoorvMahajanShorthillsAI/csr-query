# CSR Multimodal AI Agent

An AI-powered pipeline for extracting data from Clinical Study Report (CSR) PDFs and performing multimodal natural language queries.

## 🚀 Features

- **Automated Extraction**: Specialized scripts for extracting tables and figures from complex clinical PDFs.
- **Multimodal Retrieval**: TF-IDF based retrieval engine that indexes text, markdown tables, and figure metadata.
- **AI Query Agent**: Natural language interface powered by Gemini 2.5 Pro for deep clinical reasoning.
- **Visual Intelligence**: Direct integration with Gemini's vision capabilities to "see" and interpret figures/charts.

## 🛠️ Project Structure

- `extract_tables_master.py`: Entry point for table extraction.
- `extract_figures_master.py`: Entry point for figure extraction.
- `table_extraction_logic/` & `figure_extraction_logic/`: Specialized logic per PDF.
- `query_agent.py`: The brain — multimodal LLM orchestration.
- `ingestion.py` & `retrieval.py`: Data loading and searchable indexing.
- `demo.py`: End-to-end clinical query demonstration.

## 📦 Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your Google AI Studio API Key:
   ```bash
   # Windows
   set GEMINI_API_KEY=your_api_key_here
   # Linux/Mac
   export GEMINI_API_KEY=your_api_key_here
   ```

## 🔍 Usage

### 1. Run Extraction
Ensure your PDFs are in the `Input documents for CSR/` folder, then run:
```bash
python extract_tables_master.py
python extract_figures_master.py
```

### 2. Run AI Query Agent
Execute clinical queries via the demo script or CLI:
```bash
python demo.py
# OR
python query_agent.py "What was the reactogenicity profile in adults >55 years?"
```

## 📄 License
[Insert License Here]
