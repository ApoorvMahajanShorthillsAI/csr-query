"""
query_agent.py — Multimodal Google Generative AI-powered CSR query agent.

Usage (programmatic):
    from query_agent import answer
    result = answer("What were the main safety findings?")

Usage (CLI):
    python query_agent.py "Your question here"
"""

import os
import sys
import json
import logging
from pathlib import Path
import PIL.Image
import io
import base64

import google.generativeai as genai

from ingestion import load_all_assets
from retrieval import retrieve

logging.basicConfig(level=logging.INFO, format="[agent] %(message)s")
logger = logging.getLogger(__name__)

# ── Model configuration ─────────────────────────────────────────────────────
MODEL_NAME = "gemini-2.5-pro"

SYSTEM_PROMPT = """You are a senior clinical study expert analyzing Pfizer-BioNTech BNT162b2 \
COVID-19 vaccine Clinical Study Report (CSR) documents.

You have been provided with:
- Relevant excerpts of raw document text from multiple CSR PDFs
- Extracted data tables in GitHub-flavored markdown format
- Extracted figures as images (charts, graphs, diagrams)

Your role:
1. Answer the user's clinical/scientific question thoroughly and accurately
2. Ground every claim in the provided sources — cite the source PDF and page number
3. Interpret data in tables and figures directly — do not speculate beyond what is shown
4. Structure your answer clearly: summary → key findings → supporting evidence
5. If a table or figure is directly relevant, explain what it shows and why it matters
6. Be precise with numbers, percentages, and statistical values from the data

Always end your response with a "Sources" section listing every PDF and page you referenced."""


def _build_parts(query: str, retrieved: dict) -> list:
    """Build the multimodal parts list for Gemini."""

    text_chunks = retrieved.get("text_chunks", [])
    tables = retrieved.get("tables", [])
    figures = retrieved.get("figures", [])

    # ── Assemble context text ────────────────────────────────────────────────
    context_parts = [f"## User Query\n{query}\n"]

    if text_chunks:
        context_parts.append("## Relevant Document Text")
        for chunk in text_chunks:
            context_parts.append(
                f"### [{chunk['source_pdf']}.pdf — Page {chunk['page_number']}]\n"
                f"{chunk['content'][:1500]}"
            )

    context_text = "\n\n".join(context_parts)

    # ── Build parts list ─────────────────────────────────────────────────────
    parts = [context_text]

    # Tables — inline markdown
    if tables:
        for tbl in tables:
            table_header = (
                f"## Table: {tbl['caption']}\n"
                f"**Source**: {tbl['source_pdf']}.pdf  |  "
                f"**Page**: {tbl.get('page_number', 'N/A')}  |  "
                f"**Section**: {tbl.get('section', 'N/A')}\n\n"
            )
            # Truncate very large tables to avoid token overflow
            table_content = tbl["content"]
            if len(table_content) > 4000:
                table_content = table_content[:4000] + "\n\n_[Table truncated for brevity]_"

            parts.append(table_header + table_content)

    # Figures — Image objects + caption text
    if figures:
        for fig in figures:
            # Caption text first
            fig_caption = (
                f"## Figure: {fig['caption']}\n"
                f"**Figure ID**: {fig['figure_id']}  |  "
                f"**Source**: {fig['source_pdf']}.pdf  |  "
                f"**Page**: {fig.get('page_number', 'N/A')}  |  "
                f"**Method**: {fig.get('method', 'N/A')}\n"
                f"**Description**: {fig.get('description', '')}"
            )
            parts.append(fig_caption)

            # Image object
            try:
                img_data = base64.b64decode(fig['base64'])
                img = PIL.Image.open(io.BytesIO(img_data))
                parts.append(img)
            except Exception as e:
                logger.warning(f"Could not process image for {fig['figure_id']}: {e}")

    return parts


def _extract_sources(retrieved: dict) -> list:
    """Build a deduplicated list of cited sources from retrieved records."""
    seen = set()
    sources = []
    all_records = (
        retrieved.get("text_chunks", [])
        + retrieved.get("tables", [])
        + retrieved.get("figures", [])
    )
    for r in all_records:
        key = (r["source_pdf"], r.get("page_number"))
        if key not in seen:
            seen.add(key)
            sources.append({"pdf": r["source_pdf"], "page": r.get("page_number")})
    return sorted(sources, key=lambda x: (x["pdf"], x["page"] or 0))


def answer(
    query: str,
    base_dir: str = ".",
    assets: dict = None,
    top_k_tables: int = 3,
    top_k_figures: int = 3,
    top_k_text: int = 5,
) -> dict:
    """
    Run a full query against all CSR assets.

    Args:
        query:         Natural language question.
        base_dir:      Path to csr/ root directory.
        assets:        Pre-loaded assets dict (if None, loads from disk). Pass this
                       on repeated queries to avoid re-loading.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not set.")

    # Configure Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT
    )

    # Load assets if not pre-loaded
    if assets is None:
        logger.info("Loading assets from disk…")
        assets = load_all_assets(base_dir)

    # Retrieve relevant assets
    logger.info(f"Retrieving for query: '{query[:80]}'")
    retrieved = retrieve(
        query,
        assets,
        top_k_tables=top_k_tables,
        top_k_figures=top_k_figures,
        top_k_text=top_k_text,
    )

    # Build multimodal parts
    parts = _build_parts(query, retrieved)

    # Call Gemini
    logger.info(f"Calling {MODEL_NAME}…")
    try:
        response = model.generate_content(parts)
        llm_answer = response.text
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        llm_answer = f"[LLM Error: {e}]"

    # Build structured result
    tables_used = [
        {
            "source_pdf": t["source_pdf"],
            "table_id": t["table_id"],
            "caption": t["caption"],
            "page_number": t.get("page_number"),
            "file_path": t["file_path"],
        }
        for t in retrieved["tables"]
    ]
    figures_used = [
        {
            "source_pdf": f["source_pdf"],
            "figure_id": f["figure_id"],
            "caption": f["caption"],
            "page_number": f.get("page_number"),
            "file_path": f["file_path"],
        }
        for f in retrieved["figures"]
    ]

    return {
        "query": query,
        "answer": llm_answer,
        "sources_cited": _extract_sources(retrieved),
        "tables_used": tables_used,
        "figures_used": figures_used,
    }


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def _print_result(result: dict):
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"QUERY: {result['query']}")
    print(bar)
    print("\nANSWER:")
    print(result["answer"])

    print("\n── TABLES USED ──")
    if result["tables_used"]:
        for t in result["tables_used"]:
            print(f"  [{t['source_pdf']}] {t['table_id']} — {t['caption']} (pg {t['page_number']})")
    else:
        print("  (none)")

    print("\n── FIGURES USED ──")
    if result["figures_used"]:
        for f in result["figures_used"]:
            print(f"  [{f['source_pdf']}] {f['figure_id']} — {f['caption']} (pg {f['page_number']})")
            print(f"    → {f['file_path']}")
    else:
        print("  (none)")

    print("\n── SOURCES CITED ──")
    for s in result["sources_cited"]:
        print(f"  {s['pdf']}.pdf — page {s['page']}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query_agent.py \"Your question here\"")
        sys.exit(1)
    query_input = " ".join(sys.argv[1:])
    res = answer(query_input)
    _print_result(res)
