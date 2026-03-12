"""
Step 3: Link cropped PDFFigures2 images to chunks.
Adds figure_paths (paths to image files) to each chunk based on figure_refs.
"""

import argparse
import json
import re
from pathlib import Path

# Cropped filenames from crop_figures.py: {paper_stem}_page{NN}_{fig_type}{fig_name}.png
# e.g. Rulerelements_page02_figure1.png -> fig_1
FIGURE_NUM_PATTERN = re.compile(r"figure(\d+)", re.IGNORECASE)
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})


def build_fig_id_to_path(
    figures_dir: Path,
    paper_stem: str | None = None,
) -> dict[str, str]:
    """
    Scan figures_dir for cropped images and map fig_N -> relative path to file.
    If paper_stem is set, figures_dir is the parent and we look in figures_dir / paper_stem.
    """
    if paper_stem:
        scan_dir = figures_dir / paper_stem
    else:
        scan_dir = figures_dir

    if not scan_dir.is_dir():
        return {}

    mapping: dict[str, str] = {}
    for f in scan_dir.iterdir():
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        m = FIGURE_NUM_PATTERN.search(f.name)
        if m:
            num = m.group(1)
            fig_id = f"fig_{num}"
            # Store path relative to figures_dir (so parent can move)
            if paper_stem:
                rel = f"{paper_stem}/{f.name}"
            else:
                rel = f.name
            mapping[fig_id] = rel
    return mapping


def link_figures_to_chunks(
    chunks: list[dict],
    figures_dir: str | Path,
    paper_stem: str | None = None,
) -> list[dict]:
    """
    Add figure_paths to each chunk. Modifies chunks in place and returns them.
    """
    figures_dir = Path(figures_dir).resolve()
    fig_to_path = build_fig_id_to_path(figures_dir, paper_stem)

    for chunk in chunks:
        refs = chunk.get("figure_refs") or []
        paths = []
        for fig_id in refs:
            if fig_id in fig_to_path:
                paths.append(fig_to_path[fig_id])
        chunk["figure_paths"] = paths

    return chunks


def _is_chunks_json(data: list) -> bool:
    """True if this looks like chunks output (list of objects with chunk_id)."""
    if not isinstance(data, list) or not data:
        return False
    first = data[0] if data else {}
    return isinstance(first, dict) and "chunk_id" in first


def _chunks_json_paths(folder: Path) -> list[Path]:
    """Return sorted paths to JSON files in folder that are chunks (from chunk_papers.py)."""
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


def _paper_stem_from_chunks_path(chunks_path: Path) -> str:
    """Infer paper stem from chunks filename, e.g. Rulerelements_chunks.json -> Rulerelements."""
    stem = chunks_path.stem
    if stem.lower().endswith("_chunks"):
        return stem[: -len("_chunks")]
    return stem


def main():
    parser = argparse.ArgumentParser(
        description="Link cropped PDFFigures2 figures to chunks (add figure_paths)."
    )
    parser.add_argument(
        "chunks_json",
        type=str,
        help="Path to chunks JSON file or folder containing *_chunks.json files",
    )
    parser.add_argument(
        "figures_dir",
        type=str,
        help="Directory containing cropped figures: paper subfolder or parent of paper subfolders (use --paper for single file)",
    )
    parser.add_argument(
        "--paper",
        type=str,
        default=None,
        help="Paper stem for single file (e.g. Rulerelements). In folder mode, stem is inferred from each filename.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output path: file (single input) or folder (folder input). Default: overwrite.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak when overwriting",
    )
    args = parser.parse_args()

    import shutil
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
                raise ValueError("For folder input, -o must be a directory or a new path.")
            out_dir.mkdir(parents=True, exist_ok=True)
        for jpath in json_paths:
            paper_stem = _paper_stem_from_chunks_path(jpath)
            with open(jpath, "r", encoding="utf-8", errors="replace") as f:
                chunks = json.load(f)
            link_figures_to_chunks(chunks, args.figures_dir, paper_stem=paper_stem)
            out_path = out_dir / jpath.name if out_dir.is_dir() else out_dir
            if out_path == jpath and not args.no_backup:
                shutil.copy2(jpath, jpath.with_suffix(jpath.suffix + ".bak"))
                print(f"Backup: {jpath.with_suffix(jpath.suffix + '.bak')}")
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
            n_with = sum(1 for c in chunks if c.get("figure_paths"))
            print(f"Written: {out_path}  (chunks with figure_paths: {n_with}/{len(chunks)})")
        print(f"Processed {len(json_paths)} file(s).")
        return

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        chunks = json.load(f)

    if not isinstance(chunks, list):
        raise ValueError("chunks_json must be a JSON array of chunks")

    link_figures_to_chunks(chunks, args.figures_dir, args.paper)

    out_path = Path(args.output).resolve() if args.output else path
    if out_path == path and not args.no_backup:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        print(f"Backup: {path.with_suffix(path.suffix + '.bak')}")

    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    n_with_paths = sum(1 for c in chunks if c.get("figure_paths"))
    print(f"Written: {out_path}")
    print(f"Chunks with at least one figure_path: {n_with_paths} / {len(chunks)}")


if __name__ == "__main__":
    main()
