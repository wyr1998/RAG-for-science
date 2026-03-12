"""
Step 4: Embed chunks using a pluggable backend (e.g. Zhipu Embedding-3).
Reads chunks JSON (single file or folder), adds "embedding" per chunk, writes back.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on path when running as script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from step4_embeddings.embedding_interface import get_backend, list_backends
from step4_embeddings.backends import *  # noqa: F401, F403 — register backends


def _is_chunks_json(data: list) -> bool:
    if not isinstance(data, list) or not data:
        return False
    first = data[0] if data else {}
    return isinstance(first, dict) and "chunk_id" in first


def _chunks_json_paths(folder: Path) -> list[Path]:
    out = []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() != ".json":
            continue
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fp:
                data = json.load(fp)
            if _is_chunks_json(data):
                out.append(f)
        except Exception:
            continue
    return out


def embed_chunks(
    chunks: list[dict],
    backend,
    text_key: str = "text",
    overwrite: bool = True,
) -> list[dict]:
    """
    Add "embedding" to each chunk. Modifies chunks in place and returns them.
    If overwrite is False, skips chunks that already have "embedding".
    """
    to_embed: list[tuple[int, str]] = []
    for i, ch in enumerate(chunks):
        if not overwrite and ch.get("embedding"):
            continue
        text = (ch.get(text_key) or "").strip() or ""
        to_embed.append((i, text))

    if not to_embed:
        return chunks

    indices = [t[0] for t in to_embed]
    texts = [t[1] for t in to_embed]
    vectors = backend.embed_texts(texts)

    for k, idx in enumerate(indices):
        chunks[idx]["embedding"] = vectors[k] if k < len(vectors) else []

    return chunks


def main():
    parser = argparse.ArgumentParser(
        description="Embed chunks with a pluggable backend (e.g. Zhipu Embedding-3)."
    )
    parser.add_argument(
        "chunks_json",
        type=str,
        help="Path to chunks JSON file or folder containing *_chunks.json files",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="zhipu_embedding3",
        help=f"Embedding backend. Available: {list_backends()}",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config for backend (api_key, dimensions, etc.). Overrides env.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file or folder. Default: overwrite input.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip chunks that already have an 'embedding' field",
    )
    args = parser.parse_args()

    config: dict = {}
    if args.config:
        config_path = Path(args.config).resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Config not found: {config_path}")
        with open(config_path, "r", encoding="utf-8", errors="replace") as f:
            config = json.load(f)
    # Allow config file next to script
    default_config = Path(__file__).resolve().parent / "config.json"
    if not config and default_config.is_file():
        with open(default_config, "r", encoding="utf-8", errors="replace") as f:
            config = json.load(f)
    # Backend-specific section (e.g. config["zhipu_embedding3"]) or whole config
    backend_section = config.get(args.backend)
    backend_config = backend_section if isinstance(backend_section, dict) else config

    backend = get_backend(args.backend, backend_config)

    path = Path(args.chunks_json).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")

    if path.is_dir():
        json_paths = _chunks_json_paths(path)
        if not json_paths:
            print("No chunks JSON files found in folder.")
            return
        out_dir = Path(args.output).resolve() if args.output else path
        if args.output:
            if out_dir.exists() and not out_dir.is_dir():
                raise ValueError("For folder input, -o must be a directory or new path.")
            out_dir.mkdir(parents=True, exist_ok=True)
        for jpath in json_paths:
            with open(jpath, "r", encoding="utf-8", errors="replace") as f:
                chunks = json.load(f)
            embed_chunks(chunks, backend, overwrite=not args.no_overwrite)
            out_path = out_dir / jpath.name if out_dir.is_dir() else out_dir
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
            n_emb = sum(1 for c in chunks if c.get("embedding"))
            print(f"Written: {out_path}  (chunks with embedding: {n_emb}/{len(chunks)})")
        print(f"Processed {len(json_paths)} file(s).")
        return

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        chunks = json.load(f)
    if not isinstance(chunks, list):
        raise ValueError("chunks_json must be a JSON array of chunks.")

    embed_chunks(chunks, backend, overwrite=not args.no_overwrite)

    out_path = Path(args.output).resolve() if args.output else path
    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    n_emb = sum(1 for c in chunks if c.get("embedding"))
    print(f"Written: {out_path}")
    print(f"Chunks with embedding: {n_emb} / {len(chunks)}")


if __name__ == "__main__":
    main()
