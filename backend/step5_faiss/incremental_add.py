"""
Step 5 (incremental): append new paper chunks to FAISS index and SQLite DB.

Usage (from project root):
    python step5_faiss/incremental_add.py \\
      NEW_CHUNKS_JSON \\
      --faiss-index indexes/papers.faiss \\
      --sqlite-db indexes/chunks.db \\
      --backend zhipu_embedding3 \\
      --embed-config step4_embeddings/config.json

This script:
  - Embeds all chunks in NEW_CHUNKS_JSON that are missing an "embedding" field.
  - Appends their vectors to an existing FAISS index (no rebuild).
  - Appends metadata rows to SQLite with matching faiss_id values.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, List, Dict

import faiss  # type: ignore
import numpy as np

# Allow running as script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from step4_embeddings.embedding_interface import get_backend, list_backends
from step4_embeddings.backends import *  # noqa: F401, F403
from step6_sqlite.sqlite_storage import _ensure_schema  # reuse schema helper


def _load_embed_backend(name: str, config_path: str | None) -> Any:
    config: dict = {}
    if config_path:
        cp = Path(config_path).resolve()
        if not cp.is_file():
            raise FileNotFoundError(f"Embedding config not found: {cp}")
        with open(cp, "r", encoding="utf-8", errors="replace") as f:
            cfg = json.load(f)
        section = cfg.get(name)
        config = section if isinstance(section, dict) else cfg
    return get_backend(name, config)


def _embed_new_chunks(chunks: List[Dict[str, Any]], backend) -> List[Dict[str, Any]]:
    """Embed chunks that are missing 'embedding'. Modifies chunks in place and returns them."""
    to_embed_indices: List[int] = []
    texts: List[str] = []
    for i, ch in enumerate(chunks):
        emb = ch.get("embedding")
        if emb:
            continue
        text = (ch.get("text") or "").strip()
        to_embed_indices.append(i)
        texts.append(text)

    if not texts:
        return chunks

    vectors = backend.embed_texts(texts)
    if len(vectors) != len(to_embed_indices):
        raise ValueError(
            f"Embedding backend returned {len(vectors)} vectors for {len(to_embed_indices)} texts."
        )

    for idx, vec in zip(to_embed_indices, vectors):
        chunks[idx]["embedding"] = vec

    return chunks


def _append_to_faiss(index_path: Path, vectors: np.ndarray) -> int:
    """Append vectors to FAISS index. Returns starting faiss_id for the new batch."""
    if not index_path.is_file():
        raise FileNotFoundError(f"FAISS index not found: {index_path}")

    index = faiss.read_index(str(index_path))
    d = index.d
    if vectors.shape[1] != d:
        raise ValueError(
            f"Vector dim {vectors.shape[1]} does not match index dim {d}. "
            "Did embeddings change since the index was built?"
        )

    # Normalize for cosine similarity (IndexFlatIP, same as in faiss_storage).
    faiss.normalize_L2(vectors)

    start_id = index.ntotal
    index.add(vectors)
    faiss.write_index(index, str(index_path))
    print(f"Appended {vectors.shape[0]} vectors to FAISS index starting at id {start_id}.")
    return start_id


def _append_to_sqlite(
    db_path: Path,
    chunks: List[Dict[str, Any]],
    start_faiss_id: int,
    paper_path: Path,
) -> None:
    """Append metadata rows for chunks to SQLite with faiss_id starting at start_faiss_id."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()

        file_name = paper_path.name

        # Optional consistency check: see existing max faiss_id
        cur.execute("SELECT MAX(faiss_id) FROM chunks")
        row = cur.fetchone()
        max_existing = row[0] if row and row[0] is not None else -1
        if max_existing != -1 and max_existing + 1 != start_faiss_id:
            print(
                f"Warning: existing max faiss_id={max_existing}, "
                f"but FAISS start id is {start_faiss_id}. "
                "Indices may be out of sync."
            )

        for local_idx, ch in enumerate(chunks):
            emb = ch.get("embedding")
            if not emb:
                continue

            faiss_id = start_faiss_id + local_idx
            chunk_id = ch.get("chunk_id") or ""
            section = ch.get("section") or ""
            text = ch.get("text") or ""
            doi = ch.get("doi") or ""
            journal = ch.get("journal") or ""
            publication_date = ch.get("publication_date") or ""
            title = ch.get("title") or ""

            figure_refs = json.dumps(ch.get("figure_refs") or [])
            figure_paths = json.dumps(ch.get("figure_paths") or [])
            figure_captions = json.dumps(ch.get("figure_captions") or [])

            cur.execute(
                """
                INSERT INTO chunks (
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
                    figure_captions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    faiss_id,
                    str(paper_path),
                    file_name,
                    local_idx,
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
                ),
            )

        conn.commit()
        print(f"Appended {len(chunks)} rows to SQLite at {db_path}.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally append new paper chunks to FAISS index and SQLite DB.",
    )
    parser.add_argument(
        "chunks_json",
        type=str,
        help="Path to *_chunks.json for a single paper (must contain text; embeddings will be added if missing).",
    )
    parser.add_argument(
        "--faiss-index",
        type=str,
        required=True,
        help="Path to existing FAISS index (e.g. indexes/papers.faiss).",
    )
    parser.add_argument(
        "--sqlite-db",
        type=str,
        required=True,
        help="Path to existing SQLite DB (e.g. indexes/chunks.db).",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="zhipu_embedding3",
        help=f"Embedding backend for new chunks (default: zhipu_embedding3). Available: {list_backends()}",
    )
    parser.add_argument(
        "--embed-config",
        type=str,
        default="step4_embeddings/config.json",
        help="Path to embedding backend config JSON (default: step4_embeddings/config.json).",
    )
    args = parser.parse_args()

    chunks_path = Path(args.chunks_json).resolve()
    if not chunks_path.is_file():
        raise FileNotFoundError(f"Chunks JSON not found: {chunks_path}")

    with open(chunks_path, "r", encoding="utf-8", errors="replace") as f:
        chunks = json.load(f)
    if not isinstance(chunks, list):
        raise ValueError("chunks_json must be a JSON array of chunks.")

    backend = _load_embed_backend(args.backend, args.embed_config)
    _embed_new_chunks(chunks, backend)

    # Save embeddings back to JSON
    with open(chunks_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"Updated embeddings written back to {chunks_path}")

    # Prepare vectors for FAISS
    vectors_list: List[List[float]] = [ch["embedding"] for ch in chunks if ch.get("embedding")]
    if not vectors_list:
        print("No embeddings found to append; nothing to do.")
        return
    vectors = np.asarray(vectors_list, dtype="float32")
    if vectors.ndim != 2:
        raise ValueError(f"Embeddings array must be 2D, got shape {vectors.shape}")

    faiss_index_path = Path(args.faiss_index).resolve()
    start_id = _append_to_faiss(faiss_index_path, vectors)

    sqlite_db_path = Path(args.sqlite_db).resolve()
    _append_to_sqlite(sqlite_db_path, chunks, start_id, paper_path=chunks_path)


if __name__ == "__main__":
    main()

