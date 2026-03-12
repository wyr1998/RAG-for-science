"""
Step 8: Call LLM to answer questions based on structured context.

The main entry point is:

    answer_question(query: str, context: list[dict], config_path: str | None = None) -> str

`context` is expected to be the `llm_context` list produced by
`step7_query/query_pipeline.py` (paper-level objects with `chunks`).

Which LLM is used is determined by config file (default: step8_llm/config.json).
Set "backend" to the backend name and add a section with the same name for options.

CLI (retrieval + LLM in one go):
    python step8_llm/llm_answer.py --query "..." --faiss-index ... --sqlite-db ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

# Ensure project root on path for step7_query
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Import backends so they register
from step8_llm.backends import *  # noqa: F401, F403
from step8_llm.llm_interface import get_llm_backend, list_llm_backends


def format_context_for_llm(context: List[Dict[str, Any]]) -> str:
    """Convert structured context (llm_context list) into a single text block for the LLM."""
    parts: List[str] = []
    for paper in context:
        title = paper.get("title") or "(no title)"
        journal = paper.get("journal") or ""
        year = paper.get("year") or ""
        doi = paper.get("doi") or ""
        header = f"Title: {title}"
        if journal or year:
            header += f" ({journal}, {year})"
        if doi:
            header += f" [DOI: {doi}]"
        parts.append(header)

        for ch in paper.get("chunks") or []:
            section = ch.get("section") or ""
            score = ch.get("score", 0.0)
            text = ch.get("text") or ""
            caps = ch.get("figure_captions") or []

            chunk_lines = []
            if section:
                chunk_lines.append(f"Section: {section}")
            chunk_lines.append(f"Relevance score: {score:.3f}")
            chunk_lines.append("Text:")
            chunk_lines.append(text.strip())
            if caps:
                chunk_lines.append("Figure captions:")
                for cap in caps:
                    chunk_lines.append(f"- {cap}")
            parts.append("\n".join(chunk_lines))

    return "\n\n---\n\n".join(parts)


def load_llm_config(config_path: str | Path | None) -> dict:
    """Load config dict. If path is None, use step8_llm/config.json if it exists."""
    if config_path is not None:
        path = Path(config_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"LLM config not found: {path}")
    else:
        path = Path(__file__).resolve().parent / "config.json"
        if not path.is_file():
            return {"backend": "zhipu", "zhipu": {}}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        cfg = json.load(f)
    return cfg


def answer_question(
    query: str,
    context: List[Dict[str, Any]],
    config_path: str | Path | None = None,
    config_overrides: dict | None = None,
) -> str:
    """
    Answer the question using the given context and the LLM selected in config.

    - query: user question.
    - context: llm_context list from retrieval (paper-level with chunks).
    - config_path: path to JSON config. If None, uses step8_llm/config.json.
    - config_overrides: optional dict merged into the backend section (e.g. {"zhipu": {"api_key": "..."}}).

    Config format:
      {
        "backend": "zhipu",
        "zhipu": { "model": "glm-4", "api_key_env": "ZHIPUAI_API_KEY" }
      }

    Returns the model's answer as plain text.
    """
    cfg = load_llm_config(config_path)
    backend_name = cfg.get("backend", "zhipu")
    backend_section = cfg.get(backend_name)
    backend_config = dict(backend_section) if isinstance(backend_section, dict) else {}
    if config_overrides:
        overrides = config_overrides.get(backend_name, config_overrides)
        if isinstance(overrides, dict):
            backend_config = {**backend_config, **overrides}
    backend = get_llm_backend(backend_name, backend_config)

    context_text = format_context_for_llm(context)
    return backend.answer(query, context_text)


def main() -> None:
    """Run retrieval (FAISS + SQLite) then LLM; print the answer."""
    parser = argparse.ArgumentParser(
        description="Answer a question: run retrieval then call LLM (config-driven).",
    )
    parser.add_argument("--query", type=str, required=True, help="Your question.")
    parser.add_argument(
        "--faiss-index",
        type=str,
        required=True,
        help="Path to FAISS index (e.g. indexes/papers.faiss).",
    )
    parser.add_argument(
        "--sqlite-db",
        type=str,
        required=True,
        help="Path to SQLite DB (e.g. indexes/chunks.db).",
    )
    parser.add_argument(
        "--llm-config",
        type=str,
        default="step8_llm/config.json",
        help="Path to LLM config JSON (default: step8_llm/config.json).",
    )
    parser.add_argument(
        "--embed-config",
        type=str,
        default="step4_embeddings/config.json",
        help="Path to embedding config for retrieval (default: step4_embeddings/config.json).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=50,
        help="Number of chunks to retrieve before paper aggregation.",
    )
    parser.add_argument(
        "--paper-top-k",
        type=int,
        default=5,
        help="Number of top papers to use as context.",
    )
    parser.add_argument(
        "--llm-chunks-per-paper",
        type=int,
        default=3,
        help="Chunks per paper in LLM context.",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="zhipu_embedding3",
        help="Embedding backend for retrieval.",
    )
    args = parser.parse_args()

    # Resolve config paths relative to project root when not absolute
    def _resolve_config(p: str) -> str:
        path = Path(p)
        return str(path) if path.is_absolute() else str(_ROOT / p)

    embed_config = _resolve_config(args.embed_config)
    llm_config = _resolve_config(args.llm_config)

    from step7_query.query_pipeline import run_retrieval

    retrieval_args = SimpleNamespace(
        query=args.query,
        faiss_index=args.faiss_index,
        sqlite_db=args.sqlite_db,
        backend=args.backend,
        config=embed_config,
        top_k=args.top_k,
        paper_aggregate=True,
        paper_top_k=args.paper_top_k,
        llm_chunks_per_paper=args.llm_chunks_per_paper,
    )
    output = run_retrieval(retrieval_args)
    llm_context = output.get("llm_context") or []

    answer = answer_question(args.query, llm_context, config_path=llm_config)
    print(answer)


if __name__ == "__main__":
    main()
