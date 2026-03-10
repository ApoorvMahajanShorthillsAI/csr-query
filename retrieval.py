"""
retrieval.py — TF-IDF + cosine similarity retrieval over ingested assets.

Exposes:
    retrieve(query, assets, top_k_tables=3, top_k_figures=3, top_k_text=5) -> dict
"""

import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


def _rank(query: str, records: list, top_k: int) -> list:
    """
    Rank records by TF-IDF cosine similarity to the query.
    Returns top_k records sorted by descending score.
    """
    if not records:
        return []

    blobs = [r.get("_search_blob", "") for r in records]
    corpus = blobs + [query]

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=20000,
            sublinear_tf=True,
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except Exception as e:
        logger.warning(f"TF-IDF vectorization failed: {e}")
        return records[:top_k]

    query_vec = tfidf_matrix[-1]          # last entry is the query
    doc_vecs = tfidf_matrix[:-1]          # all records

    scores = cosine_similarity(query_vec, doc_vecs).flatten()
    ranked_indices = np.argsort(scores)[::-1][:top_k]

    return [records[i] for i in ranked_indices]


def retrieve(
    query: str,
    assets: dict,
    top_k_tables: int = 3,
    top_k_figures: int = 3,
    top_k_text: int = 5,
) -> dict:
    """
    Retrieve the most relevant tables, figures, and text chunks for a query.

    Args:
        query:         Natural language query string.
        assets:        Dict returned by ingestion.load_all_assets().
        top_k_tables:  How many table records to return.
        top_k_figures: How many figure records to return.
        top_k_text:    How many text chunk records to return.

    Returns:
        {
            "tables":      [top_k_tables most relevant table records],
            "figures":     [top_k_figures most relevant figure records],
            "text_chunks": [top_k_text most relevant text records],
        }
    """
    tables = _rank(query, assets.get("tables", []), top_k_tables)
    figures = _rank(query, assets.get("figures", []), top_k_figures)
    text_chunks = _rank(query, assets.get("text_chunks", []), top_k_text)

    logger.info(
        f"Retrieved {len(tables)} tables, {len(figures)} figures, "
        f"{len(text_chunks)} text chunks for query: '{query[:60]}...'"
    )

    return {
        "tables": tables,
        "figures": figures,
        "text_chunks": text_chunks,
    }
