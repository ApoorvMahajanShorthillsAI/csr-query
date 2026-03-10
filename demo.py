"""
demo.py — Runs 3 expert clinical queries against the CSR document corpus.

Each query is designed to pull in both tables AND figures from across
the 9 source PDFs, exercising multimodal retrieval fully.

Run:
    set LITELLM_API_KEY=sk-...   (Windows)
    python demo.py
"""

import os
import sys
import time
from pathlib import Path

# Ensure we run from the csr/ root
BASE_DIR = str(Path(__file__).parent.resolve())

from ingestion import load_all_assets
from query_agent import answer, _print_result

# ── 3 Expert Clinical Queries ─────────────────────────────────────────────────
# These are crafted to specifically target the richest content across all PDFs:
#
# Q1 — Immunogenicity (IB + Reports + Results): pulls IgG GMC tables from IB/Reports,
#       neutralising antibody figures (Fig 10, 11, 25-32 from IB, Figs 3-8 from Reports,
#       and Figs 2-4 from Results) → high figure+table yield.
#
# Q2 — Safety & Reactogenicity (Protocol + IB + AE): pulls local/systemic reaction tables
#       from Protocol and IB, and the safety landscape figures (Figs 33-38 IB,
#       Figs 9-13 Protocol, Figs A3.3-A3.6 Protocol) → complex mixed retrieval.
#
# Q3 — Statistical methodology & dose optimisation (SAP + IB + Reports):
#       pulls SAP probability/multiplicity tables, dose-response tables from IB,
#       VN50 titer figures from Reports → tests retrieval across methodology PDFs.

QUERIES = [
    {
        "label": "Query 1 — Immunogenicity & Antibody Response",
        "query": (
            "Across the BNT162b2 clinical studies, what was the magnitude and trajectory "
            "of the humoral immune response — specifically SARS-CoV-2 neutralizing antibody "
            "titers (VN50/NT50) and S1-binding or RBD-binding IgG GMCs — in younger adults "
            "(18–55 years) versus elderly adults (≥56 years) after the two-dose regimen? "
            "Include all supporting tables and figures comparing dose groups and age cohorts. "
            "Cite the specific study (BNT162-01, BNT162-02, Phase 2/3) for each data point."
        ),
    },
    {
        "label": "Query 2 — Reactogenicity & Safety Profile",
        "query": (
            "What was the reactogenicity profile of BNT162b2 in the clinical programme? "
            "Describe local reactions (injection-site pain, redness, swelling) and systemic "
            "events (fatigue, headache, fever, chills, myalgia) reported after doses 1 and 2, "
            "broken down by age group (16–55 years vs >55 years). "
            "How did the severity profile change between the two dose administrations? "
            "Provide data from all relevant safety tables and reference the corresponding "
            "bar-chart figures from the reports."
        ),
    },
    {
        "label": "Query 3 — Statistical Analysis Plan & Dose Optimisation",
        "query": (
            "Summarise the statistical methodology used in the BNT162b2 efficacy analysis: "
            "the primary endpoint definition, the vaccine efficacy calculation formula, "
            "multiplicity adjustment strategy, and the criteria used to select the 30 µg dose "
            "as the optimal dose over lower doses (1, 3, 10, 20 µg). "
            "Include the multiplicity schema figure and any dose-selection tables that show "
            "immunogenicity data across dose levels from the Investigator's Brochure and "
            "the Statistical Analysis Plan."
        ),
    },
]


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    print("=" * 70)
    print("CSR AI QUERY AGENT — DEMO")
    print("=" * 70)
    print(f"\nLoading all assets from: {BASE_DIR}")
    print("(This may take 1-2 minutes for PDF text extraction…)\n")

    # Load once, reuse across all 3 queries
    assets = load_all_assets(BASE_DIR)

    print(f"\n✓ Assets loaded:")
    print(f"  Tables:      {len(assets['tables'])}")
    print(f"  Figures:     {len(assets['figures'])}")
    print(f"  Text chunks: {len(assets['text_chunks'])}")
    print()

    for i, q in enumerate(QUERIES, start=1):
        print(f"\n{'#' * 70}")
        print(f"# RUNNING {q['label'].upper()}")
        print(f"{'#' * 70}")

        start = time.time()
        result = answer(
            query=q["query"],
            base_dir=BASE_DIR,
            assets=assets,           # reuse pre-loaded assets
            top_k_tables=3,
            top_k_figures=3,
            top_k_text=5,
        )
        elapsed = time.time() - start

        _print_result(result)
        print(f"[Completed in {elapsed:.1f}s]\n")

        # Small pause between API calls
        if i < len(QUERIES):
            time.sleep(2)

    print("\n" + "=" * 70)
    print("DEMO COMPLETE — All 3 queries executed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
