"""
Step 1: Process PDF papers with GROBID to extract structured content.
Requires: Docker Desktop (with GROBID container running) + Anaconda env "knowledgebase"
"""
from pathlib import Path

try:
    from grobid_client.grobid_client import GrobidClient
except ImportError:
    raise ImportError(
        "Install grobid-client-python: pip install grobid-client-python\n"
        "(Note: grobid-client is a different package; use grobid-client-python for this script)"
    )


def process_pdfs(
    input_path: str | Path,
    output_path: str | Path | None = None,
    config_path: str | Path = "config.json",
    n_concurrent: int = 5,
    json_output: bool = True,
    markdown_output: bool = False,
):
    """
    Process PDF files with GROBID and save structured output (TEI XML, optionally JSON/Markdown).

    Args:
        input_path: Path to a PDF file or folder containing PDFs
        output_path: Where to save output. Defaults to same dir as input with "_grobid_output"
        config_path: Path to GROBID config (default: config.json)
        n_concurrent: Number of concurrent requests
        json_output: Also produce JSON (CORD-19-like structure)
        markdown_output: Also produce Markdown
    """
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    # GROBID client expects a directory; use parent dir when input is a file
    input_dir = input_path.parent if input_path.is_file() else input_path

    if output_path is None:
        output_path = input_dir / f"{input_path.stem}_grobid_output"
    else:
        output_path = Path(output_path).resolve()

    config_file = Path(config_path)
    if config_file.exists():
        client = GrobidClient(config_path=str(config_file))
    else:
        # Use defaults (localhost:8070)
        client = GrobidClient(grobid_server="http://localhost:8070")

    client.process(
        service="processFulltextDocument",
        input_path=str(input_dir),
        output=str(output_path),
        n=n_concurrent,
        consolidate_header=True,
        consolidate_citations=True,
        json_output=json_output,
        markdown_output=markdown_output,
        verbose=True,
    )
    print(f"\nDone. Output saved to: {output_path}")
