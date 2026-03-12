"""
Step 5: Build a FAISS index from chunk embeddings.

Usage:
    python step5_faiss/faiss.py INPUT_FOLDER INDEX_PATH [--cpu-only]

INPUT_FOLDER:
    Folder containing *_chunks.json files with an `embedding` field per chunk
    (output of step4_embeddings/embed_chunks.py).

INDEX_PATH:
    Path to write the FAISS index file (e.g. indexes/papers.faiss).

FAISS:
    Install GPU build if available (recommended):
        pip install faiss-gpu
    or CPU-only:
        pip install faiss-cpu
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import faiss  # type: ignore


def _is_chunks_with_embeddings(data) -> bool:
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


def load_embeddings_from_folder(folder: Path) -> np.ndarray:
    """
    Load all embeddings from *_chunks.json files in a folder.

    Returns:
        np.ndarray of shape (n_chunks, dim), dtype float32.
    """
    paths = _chunks_json_paths(folder)
    if not paths:
        raise ValueError(f"No chunks JSON files with embeddings found in {folder}")

    vectors: list[list[float]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for ch in data:
            emb = ch.get("embedding")
            if not emb:
                continue
            vectors.append(list(emb))

    if not vectors:
        raise ValueError(f"No embeddings found in chunks under {folder}")

    arr = np.asarray(vectors, dtype="float32")
    if arr.ndim != 2:
        raise ValueError(f"Embeddings array must be 2D, got shape {arr.shape}")

    # Normalize in-place so we can use cosine similarity (via inner product).
    faiss.normalize_L2(arr)
    return arr


def build_faiss_index(vectors: np.ndarray, use_gpu: bool = True) -> faiss.Index:
    """
    Build a cosine-similarity FAISS index from vectors.

    If use_gpu is True and GPU FAISS is available, indexing is accelerated on GPU
    and converted back to CPU index before saving.
    """
    n, d = vectors.shape
    if n == 0:
        raise ValueError("No vectors to index")

    # Vectors should already be L2-normalized; use inner product (cosine).
    index_cpu = faiss.IndexFlatIP(d)

    if use_gpu:
        try:
            # Try GPU acceleration if faiss-gpu is installed
            res = faiss.StandardGpuResources()
            index_gpu = faiss.index_cpu_to_gpu(res, 0, index_cpu)
            index_gpu.add(vectors)
            index = faiss.index_gpu_to_cpu(index_gpu)
            return index
        except Exception:
            # Fallback to pure CPU
            index_cpu.add(vectors)
            return index_cpu

    index_cpu.add(vectors)
    return index_cpu


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a FAISS index from chunk embeddings."
    )
    parser.add_argument(
        "input_folder",
        type=str,
        help="Folder containing *_chunks.json files with 'embedding' fields.",
    )
    parser.add_argument(
        "index_path",
        type=str,
        help="Output path for FAISS index file (e.g. indexes/papers.faiss).",
    )
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="Force CPU-only indexing even if faiss-gpu is installed.",
    )
    args = parser.parse_args()

    input_folder = Path(args.input_folder).resolve()
    if not input_folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {input_folder}")

    vectors = load_embeddings_from_folder(input_folder)
    print(f"Loaded {vectors.shape[0]} embeddings of dimension {vectors.shape[1]}")

    index = build_faiss_index(vectors, use_gpu=not args.cpu_only)

    index_path = Path(args.index_path).resolve()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    print(f"FAISS index written to {index_path}")


if __name__ == "__main__":
    main()

