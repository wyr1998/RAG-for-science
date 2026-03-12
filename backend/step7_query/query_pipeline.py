"""
Step 7: Query retrieval pipeline.

Pipeline:
  - Embed query with the same backend as chunks (e.g. Zhipu Embedding-3)
  - L2-normalize query vector
  - FAISS search (cosine similarity via inner product on normalized vectors)
  - Get top_k faiss_ids
  - Fetch metadata from SQLite
  - Return structured results (printed as JSON)

Usage:
    python step7_query/query_pipeline.py \\
        --query "Your question about the paper" \\
        --faiss-index indexes/papers.faiss \\
        --sqlite-db indexes/chunks.db \\
        [--backend zhipu_embedding3] \\
        [--config step4_embeddings/config.json] \\
        [--top-k 5]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import faiss  # type: ignore

# Ensure project root is on sys.path for embedding backends
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from step4_embeddings.embedding_interface import get_backend, list_backends
from step4_embeddings.backends import *  # noqa: F401,F403  (register backends)


def _load_backend(name: str, config_path: str | dict | None) -> Any:
    config: dict = {}
    if config_path is not None:
        if isinstance(config_path, dict):
            config = config_path
        else:
            cp = Path(config_path).resolve()
            if not cp.is_file():
                raise FileNotFoundError(f"Backend config not found: {cp}")
            with open(cp, "r", encoding="utf-8", errors="replace") as f:
                cfg = json.load(f)
            section = cfg.get(name)
            config = section if isinstance(section, dict) else cfg
    return get_backend(name, config)


def _normalize_query(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a 1D vector. Returns zero vector unchanged."""
    if vec.ndim != 1:
        raise ValueError(f"Query vector must be 1D, got shape {vec.shape}")
    norm = np.linalg.norm(vec)
    if norm > 0:
        return (vec / norm).astype("float32")
    return vec.astype("float32")


def _fetch_rows(conn: sqlite3.Connection, ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch rows from SQLite for given faiss_ids in the same order."""
    out: List[Dict[str, Any]] = []
    cur = conn.cursor()
    for fid in ids:
        cur.execute(
            "SELECT faiss_id, paper_path, file_name, chunk_index, chunk_id, "
            "section, text, doi, journal, publication_date, title, "
            "figure_refs, figure_paths, figure_captions "
            "FROM chunks WHERE faiss_id = ?",
            (int(fid),),
        )
        row = cur.fetchone()
        if not row:
            continue
        (
            faiss_id,
            paper_path,
            file_name,
            chunk_index,
            chunk_id,
            section,
            text,
            doi,
            journal,
            publication_date,
            title,
            figure_refs,
            figure_paths,
            figure_captions,
        ) = row

        def _loads_or_empty(s: str) -> Any:
            try:
                return json.loads(s) if s else []
            except Exception:
                return []

        out.append(
            {
                "faiss_id": faiss_id,
                "paper_path": paper_path,
                "file_name": file_name,
                "chunk_index": chunk_index,
                "chunk_id": chunk_id,
                "section": section,
                "text": text,
                "doi": doi,
                "journal": journal,
                "publication_date": publication_date,
                "title": title,
                "figure_refs": _loads_or_empty(figure_refs),
                "figure_paths": _loads_or_empty(figure_paths),
                "figure_captions": _loads_or_empty(figure_captions),
            }
        )
    return out


def _aggregate_by_paper(results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """
    Aggregate chunk-level results to paper-level by summing similarity scores.

    Group key preference: DOI -> file_name -> paper_path.
    """
    papers: Dict[str, Dict[str, Any]] = {}
    for r in results:
        key = r.get("doi") or r.get("file_name") or r.get("paper_path")
        if not key:
            continue
        if key not in papers:
            papers[key] = {
                "paper_key": key,
                "doi": r.get("doi") or "",
                "title": r.get("title") or "",
                "journal": r.get("journal") or "",
                "publication_date": r.get("publication_date") or "",
                "file_name": r.get("file_name") or "",
                "paper_path": r.get("paper_path") or "",
                "score_sum": 0.0,
                "score_max": float("-inf"),
                "chunk_count": 0,
                "top_chunks": [],
            }
        p = papers[key]
        score = float(r.get("score", 0.0))
        p["score_sum"] += score
        if score > p["score_max"]:
            p["score_max"] = score
        p["chunk_count"] += 1
        p["top_chunks"].append(
            {
                "faiss_id": r.get("faiss_id"),
                "score": score,
                "rank": r.get("rank"),
                "chunk_id": r.get("chunk_id"),
                "section": r.get("section"),
                "text": r.get("text"),
                "figure_paths": r.get("figure_paths") or [],
                "figure_captions": r.get("figure_captions") or [],
            }
        )

    for p in papers.values():
        # Keep top 3 chunks per paper by score
        p["top_chunks"].sort(key=lambda c: c["score"], reverse=True)
        p["top_chunks"] = p["top_chunks"][:3]
        if p["score_max"] == float("-inf"):
            p["score_max"] = 0.0

    paper_list = list(papers.values())
    paper_list.sort(key=lambda x: x["score_sum"], reverse=True)
    return paper_list[: max(1, top_k)]


def _build_llm_context(
    papers: List[Dict[str, Any]],
    chunk_results: List[Dict[str, Any]],
    chunks_per_paper: int,
) -> List[Dict[str, Any]]:
    """
    Build structured context for LLM:
      - title, journal, year
      - top-N relevant chunks per paper with text + figure captions.
    """
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for r in chunk_results:
        key = r.get("doi") or r.get("file_name") or r.get("paper_path")
        if not key:
            continue
        by_key.setdefault(key, []).append(r)

    for key, lst in by_key.items():
        lst.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)

    contexts: List[Dict[str, Any]] = []
    for p in papers:
        key = p.get("paper_key")
        if not key:
            continue
        chunks_for_paper = by_key.get(key, [])
        top_chunks = chunks_for_paper[: max(1, chunks_per_paper)]

        pub_date = p.get("publication_date") or ""
        year = ""
        if isinstance(pub_date, str) and len(pub_date) >= 4:
            year = pub_date[:4]

        ctx_chunks = []
        for c in top_chunks:
            ctx_chunks.append(
                {
                    "chunk_id": c.get("chunk_id"),
                    "section": c.get("section"),
                    "score": float(c.get("score", 0.0)),
                    "text": c.get("text") or "",
                    "figure_captions": c.get("figure_captions") or [],
                    "figure_paths": c.get("figure_paths") or [],
                }
            )

        contexts.append(
            {
                "paper_key": key,
                "doi": p.get("doi") or "",
                "title": p.get("title") or "",
                "journal": p.get("journal") or "",
                "year": year,
                "publication_date": pub_date,
                "score_sum": float(p.get("score_sum", 0.0)),
                "score_max": float(p.get("score_max", 0.0)),
                "chunk_count": int(p.get("chunk_count", 0)),
                "chunks": ctx_chunks,
            }
        )

    return contexts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query retrieval pipeline using FAISS + SQLite + embedding backend."
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Natural-language query text.",
    )
    parser.add_argument(
        "--faiss-index",
        type=str,
        required=True,
        help="Path to FAISS index file (e.g. indexes/papers.faiss).",
    )
    parser.add_argument(
        "--sqlite-db",
        type=str,
        required=True,
        help="Path to SQLite DB created by step6_sqlite/sqlite_storage.py.",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="zhipu_embedding3",
        help=f"Embedding backend (default: zhipu_embedding3). Available: {list_backends()}",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config for embedding backend (API keys, model, etc.).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top results to retrieve.",
    )
    parser.add_argument(
        "--paper-aggregate",
        action="store_true",
        help="Aggregate chunk results to paper level (sum scores per paper).",
    )
    parser.add_argument(
        "--paper-top-k",
        type=int,
        default=5,
        help="Number of top papers to return when using --paper-aggregate.",
    )
    parser.add_argument(
        "--llm-chunks-per-paper",
        type=int,
        default=3,
        help="When aggregating by paper, how many top chunks per paper to include in LLM context.",
    )
    args = parser.parse_args()
    output = run_retrieval(args)
    print(json.dumps(output, ensure_ascii=False, indent=2))


def run_retrieval(args: Any) -> Any:
    """
    Run the retrieval pipeline: embed query -> FAISS search -> fetch metadata.
    Returns the output dict (chunk list, or dict with papers/chunks/llm_context if paper_aggregate).
    """
    backend = _load_backend(args.backend, args.config)

    q_vec = backend.embed_texts([args.query])[0]
    q = np.asarray(q_vec, dtype="float32")
    q = _normalize_query(q)[None, :]

    index_path = Path(args.faiss_index).resolve()
    if not index_path.is_file():
        raise FileNotFoundError(f"FAISS index not found: {index_path}")
    index = faiss.read_index(str(index_path))

    if q.shape[1] != index.d:
        raise ValueError(
            f"Query dim {q.shape[1]} does not match index dim {index.d}. "
            "Did you rebuild the index after changing embedding model?"
        )

    top_k = max(1, args.top_k)
    scores, ids = index.search(q, top_k)
    ids_list = [int(i) for i in ids[0] if i >= 0]

    db_path = Path(args.sqlite_db).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        rows = _fetch_rows(conn, ids_list)
    finally:
        conn.close()

    results: List[Dict[str, Any]] = []
    for rank, fid in enumerate(ids_list):
        score = float(scores[0, rank])
        meta = next((r for r in rows if r["faiss_id"] == fid), None)
        if not meta:
            continue
        meta_with_score = dict(meta)
        meta_with_score["score"] = score
        meta_with_score["rank"] = rank
        results.append(meta_with_score)

    if getattr(args, "paper_aggregate", False):
        paper_results = _aggregate_by_paper(results, getattr(args, "paper_top_k", 5))
        llm_context = _build_llm_context(
            paper_results, results, getattr(args, "llm_chunks_per_paper", 3)
        )
        return {
            "papers": paper_results,
            "chunks": results,
            "llm_context": llm_context,
        }
    return results


if __name__ == "__main__":
    main()

