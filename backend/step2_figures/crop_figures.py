"""
Step 2b: Crop figures from PDFs using PyMuPDF based on PDFFigures2 coordinates.

Requires: PyMuPDF (pip install PyMuPDF in your Anaconda environment)
"""

import argparse
import json
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError(
        "PyMuPDF not installed. Install it with:\n"
        "  conda activate knowledgebase\n"
        "  pip install PyMuPDF"
    )


def crop_figures_from_pdf(
    pdf_path: str | Path,
    figures_json_path: str | Path,
    output_dir: str | Path,
    dpi: int = 300,
    format: str = "png",
):
    """
    Crop figures from a PDF using PDFFigures2 coordinates.

    Args:
        pdf_path: Path to the source PDF file
        figures_json_path: Path to PDFFigures2 output JSON (e.g., figuresRulerelements.json)
        output_dir: Directory where cropped figure images will be saved
        dpi: Resolution for output images (default: 300)
        format: Output format: "png", "jpg", "jpeg" (default: "png")
    """
    pdf_path = Path(pdf_path).resolve()
    figures_json_path = Path(figures_json_path).resolve()
    output_dir = Path(output_dir).resolve()

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not figures_json_path.is_file():
        raise FileNotFoundError(f"Figures JSON not found: {figures_json_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load PDFFigures2 output
    with open(figures_json_path, "r", encoding="utf-8") as f:
        figures = json.load(f)

    if not isinstance(figures, list):
        raise ValueError(f"Expected JSON array, got {type(figures)}")

    # Open PDF
    doc = fitz.open(str(pdf_path))
    pdf_name = pdf_path.stem

    # Calculate zoom factor for desired DPI (PDF default is 72 DPI)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    cropped_count = 0
    skipped_count = 0

    for fig in figures:
        if "regionBoundary" not in fig:
            print(f"Skipping figure '{fig.get('name', 'unknown')}': no regionBoundary")
            skipped_count += 1
            continue

        # JSON should store 1-based (real) page numbers. Run correct_pdffigures2_pages.py if needed.
        page_one_based = int(fig.get("page", 1))
        page_num = page_one_based - 1  # PyMuPDF uses 0-based page index

        if page_num < 0 or page_num >= len(doc):
            print(f"Skipping figure '{fig.get('name', 'unknown')}': invalid page {page_one_based}")
            skipped_count += 1
            continue

        # Get bounding box (PDFFigures2 uses x1, y1, x2, y2 where (0,0) is top-left)
        bbox = fig["regionBoundary"]
        x1, y1 = bbox["x1"], bbox["y1"]
        x2, y2 = bbox["x2"], bbox["y2"]

        # PyMuPDF Rect uses (x0, y0, x1, y1) where (x0,y0) is top-left
        # So we can use (x1, y1, x2, y2) directly
        rect = fitz.Rect(x1, y1, x2, y2)

        # Get page
        page = doc[page_num]

        # Crop and render
        try:
            pix = page.get_pixmap(matrix=mat, clip=rect)
        except Exception as e:
            print(f"Error cropping figure '{fig.get('name', 'unknown')}' on page {page_one_based}: {e}")
            skipped_count += 1
            continue

        # Generate filename
        fig_name = fig.get("name", "unknown")
        fig_type = fig.get("figType", "Figure").lower()
        output_filename = f"{pdf_name}_page{page_one_based:02d}_{fig_type}{fig_name}.{format}"
        output_path = output_dir / output_filename

        # Save
        pix.save(str(output_path))
        cropped_count += 1
        print(f"Cropped: {output_filename}")

    doc.close()

    print(f"\nDone. Cropped {cropped_count} figures, skipped {skipped_count}.")
    print(f"Output directory: {output_dir}")


def crop_figures_batch(
    pdf_dir: str | Path,
    figures_dir: str | Path,
    output_parent: str | Path,
    dpi: int = 300,
    format: str = "png",
) -> None:
    """
    Crop figures for all PDFs in a directory. For each PDF, find matching
    figures{stem}.json in figures_dir and write images to output_parent / {stem} /.

    Args:
        pdf_dir: Directory containing PDF files
        figures_dir: Directory containing PDFFigures2 JSONs (figuresRulerelements.json, etc.)
        output_parent: Parent output directory; one subfolder per paper is created
        dpi: Resolution for output images
        format: Output image format
    """
    pdf_dir = Path(pdf_dir).resolve()
    figures_dir = Path(figures_dir).resolve()
    output_parent = Path(output_parent).resolve()

    if not pdf_dir.is_dir():
        raise NotADirectoryError(f"PDF directory not found: {pdf_dir}")
    if not figures_dir.is_dir():
        raise NotADirectoryError(f"Figures directory not found: {figures_dir}")

    output_parent.mkdir(parents=True, exist_ok=True)

    # Collect PDFs (deduplicate: on Windows .pdf and .PDF can be the same file)
    pdf_files = sorted(set(pdf_dir.glob("*.pdf")) | set(pdf_dir.glob("*.PDF")), key=lambda p: p.name.lower())
    if not pdf_files:
        print(f"No PDFs found in {pdf_dir}")
        return

    processed = 0
    skipped = 0

    for pdf_path in pdf_files:
        stem = pdf_path.stem
        # PDFFigures2 names output as figures{stem}.json (e.g. figuresRulerelements.json)
        json_name = f"figures{stem}.json"
        figures_json_path = figures_dir / json_name
        if not figures_json_path.is_file():
            print(f"Skipping {pdf_path.name}: no {json_name} in {figures_dir}")
            skipped += 1
            continue

        paper_output = output_parent / stem
        try:
            crop_figures_from_pdf(
                pdf_path=pdf_path,
                figures_json_path=figures_json_path,
                output_dir=paper_output,
                dpi=dpi,
                format=format,
            )
            processed += 1
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")
            skipped += 1

    print(f"\nBatch done. Processed {processed} papers, skipped {skipped}.")


def main():
    parser = argparse.ArgumentParser(
        description="Crop figures from PDFs using PDFFigures2 coordinates (step 2b). "
        "Pass a PDF file + JSON file for one paper, or two directories for batch (one folder per paper)."
    )
    parser.add_argument(
        "pdf_or_pdf_dir",
        type=str,
        help="Path to a single PDF file, or directory containing multiple PDFs",
    )
    parser.add_argument(
        "figures_json_or_figures_dir",
        type=str,
        help="Path to a single PDFFigures2 JSON file, or directory containing figures*.json files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Output directory (for single PDF: images go here; for batch: one subfolder per paper)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolution for output images (default: 300)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="png",
        choices=["png", "jpg", "jpeg"],
        help="Output image format (default: png)",
    )

    args = parser.parse_args()
    pdf_input = Path(args.pdf_or_pdf_dir).resolve()
    figures_input = Path(args.figures_json_or_figures_dir).resolve()

    if pdf_input.is_dir() and figures_input.is_dir():
        crop_figures_batch(
            pdf_dir=pdf_input,
            figures_dir=figures_input,
            output_parent=args.output,
            dpi=args.dpi,
            format=args.format,
        )
    elif pdf_input.is_file() and figures_input.is_file():
        crop_figures_from_pdf(
            pdf_path=pdf_input,
            figures_json_path=figures_input,
            output_dir=args.output,
            dpi=args.dpi,
            format=args.format,
        )
    else:
        parser.error(
            "Either both inputs must be files (single paper) or both must be directories (batch). "
            f"Got: pdf={pdf_input} (file={pdf_input.is_file()}), figures={figures_input} (file={figures_input.is_file()})"
        )


if __name__ == "__main__":
    main()
