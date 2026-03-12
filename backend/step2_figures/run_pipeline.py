"""
Step 2 pipeline: run PDFFigures2 extraction and PyMuPDF cropping in one go.

Usage (from project root):
    python step2_figures/run_pipeline.py PDF_DIR --pdffigures2-dir PDFFIG2_DIR -o FIGURES_OUTPUT [--dpi 300] [--format png]

PDF_DIR:
    Directory containing PDF files.

FIGURES_OUTPUT:
    Directory where PDFFigures2 JSON (figures*.json), stats, and cropped figures will be written.
    Cropped images go under FIGURES_OUTPUT/cropped_figures/<paper_stem>/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as script: python step2_figures/run_pipeline.py
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from step2_figures.extract_figures import extract_figures_with_pdffigures2
from step2_figures.crop_figures import crop_figures_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 2 pipeline: PDFFigures2 extraction + PyMuPDF cropping.",
    )
    parser.add_argument(
        "pdf_dir",
        type=str,
        help="Directory containing PDF files to process.",
    )
    parser.add_argument(
        "--pdffigures2-dir",
        type=str,
        required=True,
        help="Path to cloned pdffigures2 repository (used as sbt working directory).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Output directory for PDFFigures2 JSON and cropped figures.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolution for cropped images (default: 300).",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="png",
        choices=["png", "jpg", "jpeg"],
        help="Image format for cropped figures (default: png).",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir).resolve()
    if not pdf_dir.is_dir():
        raise NotADirectoryError(f"PDF directory not found: {pdf_dir}")

    output_dir = Path(args.output).resolve()
    pdffigures2_dir = Path(args.pdffigures2_dir).resolve()

    # Step 2a: run PDFFigures2, write figures*.json + stats, and normalize page numbers to 1-based.
    extract_figures_with_pdffigures2(
        pdf_dir=pdf_dir,
        output_dir=output_dir,
        pdffigures2_dir=pdffigures2_dir,
        stats_file=None,
    )

    # Step 2b: crop figures for all PDFs using the figures*.json files we just wrote.
    cropped_parent = output_dir / "cropped_figures"
    crop_figures_batch(
        pdf_dir=pdf_dir,
        figures_dir=output_dir,
        output_parent=cropped_parent,
        dpi=args.dpi,
        format=args.format,
    )

    print(f"\nDone. Cropped figures written under: {cropped_parent}")


if __name__ == "__main__":
    main()

