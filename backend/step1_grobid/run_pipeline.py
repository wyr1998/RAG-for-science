"""
Step 1 pipeline: run GROBID processing, postprocess, token counts, figure refs, and chunking in one go.

Usage (from project root):
    python step1_grobid/run_pipeline.py INPUT [-o OUTPUT] [-c CONFIG] [options]
    python -m step1_grobid.run_pipeline INPUT [-o OUTPUT] [-c CONFIG] [options]

INPUT: Path to a PDF file or folder containing PDFs.
OUTPUT: Directory for GROBID output and all derived JSON (default: input_stem_grobid_output or INPUT_grobid_output).
Chunks are written to OUTPUT/chunk/<stem>_chunks.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as script: python step1_grobid/run_pipeline.py
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from step1_grobid.process_pdfs import process_pdfs
from step1_grobid.postprocess_grobid_json import run_postprocess
from step1_grobid.add_token_counts import run_add_token_counts, DEFAULT_ENCODING
from step1_grobid.add_paragraph_figure_refs import run_add_figure_refs
from step1_grobid.chunk_papers import run_chunk_papers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 1 pipeline: GROBID → postprocess → token counts → figure refs → chunking.",
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to a PDF file or folder containing PDFs",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: input folder with _grobid_output suffix)",
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to GROBID config.json (default: step1_grobid/config.json)",
    )
    parser.add_argument(
        "-n", "--concurrent",
        type=int,
        default=5,
        help="Number of concurrent GROBID requests (default: 5)",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable JSON output from GROBID",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Also output Markdown from GROBID",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak backups when overwriting JSON in postprocess steps",
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default=DEFAULT_ENCODING,
        help=f"Tiktoken encoding for token counts (default: {DEFAULT_ENCODING})",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    config_path = args.config
    if config_path is None:
        config_path = str(Path(__file__).resolve().parent / "config.json")
    output_path = Path(args.output).resolve() if args.output else None
    process_pdfs(
        input_path=input_path,
        output_path=output_path,
        config_path=config_path,
        n_concurrent=args.concurrent,
        json_output=not args.no_json,
        markdown_output=args.markdown,
    )

    # Resolve output dir: process_pdfs has already created it
    if output_path is None:
        input_dir = input_path.parent if input_path.is_file() else input_path
        output_dir = input_dir / f"{input_path.stem}_grobid_output"
    else:
        output_dir = output_path

    if not output_dir.is_dir():
        raise FileNotFoundError(f"Expected output dir: {output_dir}")

    no_backup = args.no_backup

    print("\n--- Postprocess (figures_and_tables) ---")
    run_postprocess(output_dir, output_path=None, no_backup=no_backup)

    print("\n--- Add token counts ---")
    run_add_token_counts(
        output_dir,
        output_path=None,
        encoding_name=args.encoding,
        no_backup=no_backup,
    )

    print("\n--- Add figure refs ---")
    run_add_figure_refs(output_dir, output_path=None, no_backup=no_backup)

    print("\n--- Chunk papers ---")
    chunk_dir = output_dir / "chunk"
    run_chunk_papers(output_dir, output_path=chunk_dir)

    print(f"\nDone. Chunks written to: {chunk_dir}")


if __name__ == "__main__":
    main()
