"""
Step 6: Store chunk metadata in SQLite aligned with FAISS vector positions.

Usage:
    python step6_sqlite/sqlite_storage.py INPUT_FOLDER DB_PATH

INPUT_FOLDER:
    Folder containing *_chunks.json files with an `embedding` field per chunk
    (output of step4_embeddings/embed_chunks.py), the same folder used for
    building the FAISS index (e.g. `chunk_embedding`).

DB_PATH:
    Path to the SQLite database file to create/update (e.g. `indexes/chunks.db`).

Alignment with FAISS:
    - This script walks files and chunks in the same order and with the same
      filtering as the FAISS step (only chunks that have an `embedding`).
    - It assigns a monotonically increasing `faiss_id` starting from 0 for each
      stored chunk.
    - If you also build your FAISS index from the same INPUT_FOLDER using
      `step5_faiss/faiss_storage.py`, the i-th vector in FAISS will correspond
      to the row with `faiss_id = i` in this SQLite DB.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _is_chunks_with_embeddings(data: Any) -> bool:
    """Heuristic: list of dicts with 'embedding' on the first element."""
    if not isinstance(data, list) or not data:
        return False
    first = data[0]
    return isinstance(first, dict) and "embedding" in first


def _chunks_json_paths(folder: Path) -> list[Path]:
    """Find JSON files in folder that look like chunks with embeddings."""
    out: list[Path] = []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() != ".json":
            continue
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fp:
                data = json.load(fp)
            if _is_chunks_with_embeddings(data):
                out.append(f)
        except Exception:
            continue
    return out


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create table for chunks metadata if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faiss_id INTEGER NOT NULL UNIQUE,
            paper_path TEXT,
            file_name TEXT,
            chunk_index INTEGER,
            chunk_id TEXT,
            section TEXT,
            text TEXT,
            doi TEXT,
            journal TEXT,
            publication_date TEXT,
            title TEXT,
            figure_refs TEXT,
            figure_paths TEXT,
            figure_captions TEXT,
            subcollection_path TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_faiss_id ON chunks(faiss_id)"
    )
    try:
        conn.execute("ALTER TABLE chunks ADD COLUMN subcollection_path TEXT")
    except sqlite3.OperationalError:
        pass


def store_metadata_from_folder(
    input_folder: Path,
    db_path: Path,
    subcollection_mapping_path: Path | None = None,
) -> None:
    """
    Walk chunks in INPUT_FOLDER and insert metadata rows into SQLite.

    Order and filtering match the FAISS step:
      - Files: sorted by name
      - Within each file: JSON list order
      - Only chunks where `embedding` is present/truthy

    Each such chunk gets a unique `faiss_id` (0-based).
    If subcollection_mapping_path is provided, it should be a JSON file mapping
    chunk file stem (e.g. "pdf_0") to subcollection path string (e.g. "ML/2024").
    """
    paths = _chunks_json_paths(input_folder)
    if not paths:
        raise ValueError(
            f"No chunks JSON files with embeddings found in {input_folder}"
        )

    mapping: dict[str, str] = {}
    if subcollection_mapping_path and subcollection_mapping_path.is_file():
        with open(subcollection_mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()

        # Clear any previous contents so alignment starts from faiss_id 0
        cur.execute("DELETE FROM chunks")

        faiss_id = 0
        for path in paths:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if not isinstance(data, list):
                continue

            file_name = path.name
            paper_path = str(path)
            stem = path.stem.replace("_chunks", "")
            subcollection_path = mapping.get(stem, "")

            for idx, ch in enumerate(data):
                emb = ch.get("embedding")
                if not emb:
                    continue

                # Basic fields
                chunk_id = ch.get("chunk_id") or ""
                section = ch.get("section") or ""
                text = ch.get("text") or ""
                doi = ch.get("doi") or ""
                journal = ch.get("journal") or ""
                publication_date = ch.get("publication_date") or ""
                title = ch.get("title") or ""

                # Arrays stored as JSON strings
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
                        figure_captions,
                        subcollection_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        faiss_id,
                        paper_path,
                        file_name,
                        idx,
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
                        subcollection_path,
                    ),
                )
                faiss_id += 1

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Store chunk metadata in SQLite aligned with FAISS vector positions."
        )
    )
    parser.add_argument(
        "input_folder",
        type=str,
        help="Folder containing *_chunks.json with 'embedding' (e.g. chunk_embedding).",
    )
    parser.add_argument(
        "db_path",
        type=str,
        help="SQLite database path to create/update (e.g. indexes/chunks.db).",
    )
    args = parser.parse_args()

    input_folder = Path(args.input_folder).resolve()
    if not input_folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {input_folder}")

    db_path = Path(args.db_path).resolve()
    store_metadata_from_folder(input_folder, db_path)
    print(f"Metadata stored in SQLite at {db_path}")


if __name__ == "__main__":
    main()

