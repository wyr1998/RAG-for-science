"""
Run the full ingestion pipeline (Step 1 through Step 6) on a papers folder.
Used by POST /index in api_server.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

# Ensure backend (this dir) is on path so step* modules can be imported
_BACKEND = Path(__file__).resolve().parent
_ROOT = _BACKEND.parent
if str(_BACKEND) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_BACKEND))

from step1_grobid.process_pdfs import process_pdfs
from step1_grobid.postprocess_grobid_json import run_postprocess
from step1_grobid.add_token_counts import run_add_token_counts, DEFAULT_ENCODING
from step1_grobid.add_paragraph_figure_refs import run_add_figure_refs
from step1_grobid.chunk_papers import run_chunk_papers
from grobid_docker import ensure_grobid_container_running
from step2_figures.extract_figures import extract_figures_with_pdffigures2
from step2_figures.crop_figures import crop_figures_batch
from step3_link_figures.link_figures_to_chunks import (
    link_figures_to_chunks,
    _chunks_json_paths,
    _paper_stem_from_chunks_path,
)
from step4_embeddings.embedding_interface import get_backend
from step4_embeddings.backends import *  # noqa: F401, F403
from step4_embeddings.embed_chunks import embed_chunks, _chunks_json_paths as _embed_chunk_paths
from step4_embeddings.embed_chunks import _is_chunks_json
from step5_faiss.faiss_storage import load_embeddings_from_folder, build_faiss_index
import faiss  # type: ignore
from step6_sqlite.sqlite_storage import store_metadata_from_folder


def run_index_pipeline(
    papers_folder: str | Path,
    output_base: str | Path | None = None,
    embed_api_key: str | None = None,
    embed_config_path: str | Path | None = None,
    use_gpu_faiss: bool = True,
    pdffigures2_dir_override: str | Path | None = None,
) -> dict[str, Any]:
    """
    Discover PDFs in papers_folder (and subfolders), run Step 1–6, return paths.

    Returns:
        dict with faiss_index, sqlite_db, figures_root (paths relative to project root or absolute).
    """
    papers_path = Path(papers_folder).resolve()
    if not papers_path.is_dir():
        raise FileNotFoundError(f"Papers folder not found: {papers_path}")

    pdfs = sorted(papers_path.rglob("*.pdf"))
    if not pdfs:
        raise ValueError(f"No PDF files found under {papers_path}")

    # Ensure GROBID is available (Docker container auto-start)
    ensure_grobid_container_running()

    # Flat temp dir with symlinks so step1/step2 see a single directory of PDFs
    temp_dir = Path(tempfile.mkdtemp(prefix="kb_papers_"))
    subcollection_mapping: dict[str, str] = {}
    try:
        for i, pdf in enumerate(pdfs):
            link_path = temp_dir / f"pdf_{i}.pdf"
            try:
                link_path.symlink_to(pdf)
            except OSError:
                shutil.copy2(pdf, link_path)
            relative = pdf.relative_to(papers_path)
            subcollection_path = relative.parent.as_posix() if relative.parent != Path(".") else ""
            subcollection_mapping[f"pdf_{i}"] = subcollection_path

        if output_base:
            p = Path(output_base)
            out_base = p.resolve() if p.is_absolute() else (_ROOT / output_base).resolve()
        else:
            out_base = _ROOT / "backend_output" / (papers_path.name or "papers")
        out_base.mkdir(parents=True, exist_ok=True)

        grobid_out = out_base / "grobid_output"
        step1_config = _BACKEND / "step1_grobid" / "config.json"
        if not step1_config.is_file():
            step1_config = str(step1_config)

        # Step 1: GROBID + postprocess + token counts + figure refs + chunking
        process_pdfs(
            input_path=temp_dir,
            output_path=grobid_out,
            config_path=str(step1_config),
            n_concurrent=5,
            json_output=True,
            markdown_output=False,
        )
        run_postprocess(grobid_out, output_path=None, no_backup=True)
        run_add_token_counts(grobid_out, output_path=None, encoding_name=DEFAULT_ENCODING, no_backup=True)
        run_add_figure_refs(grobid_out, output_path=None, no_backup=True)
        chunk_dir = grobid_out / "chunk"
        run_chunk_papers(grobid_out, output_path=chunk_dir)

        figures_out = out_base / "figures_output"
        pdffigures2_dir = pdffigures2_dir_override or os.environ.get("PDFFIGURES2_DIR")
        if pdffigures2_dir:
            pdffigures2_path = Path(pdffigures2_dir).resolve()
            if pdffigures2_path.is_dir():
                extract_figures_with_pdffigures2(
                    pdf_dir=temp_dir,
                    output_dir=figures_out,
                    pdffigures2_dir=pdffigures2_path,
                    stats_file=None,
                )
                cropped_parent = figures_out / "cropped_figures"
                crop_figures_batch(
                    pdf_dir=temp_dir,
                    figures_dir=figures_out,
                    output_parent=cropped_parent,
                    dpi=300,
                    format="png",
                )
                # Step 3: link figures to chunks
                figures_dir = cropped_parent
                chunk_paths = _chunks_json_paths(chunk_dir)
                for jpath in chunk_paths:
                    paper_stem = _paper_stem_from_chunks_path(jpath)
                    with open(jpath, "r", encoding="utf-8", errors="replace") as f:
                        chunks = json.load(f)
                    link_figures_to_chunks(chunks, str(figures_dir), paper_stem=paper_stem)
                    with open(jpath, "w", encoding="utf-8", errors="replace") as f:
                        json.dump(chunks, f, indent=2, ensure_ascii=False)

        # Step 4: embed chunks
        embed_cfg_path = Path(embed_config_path).resolve() if embed_config_path else (_BACKEND / "step4_embeddings" / "config.json")
        embed_cfg: dict = {}
        if embed_cfg_path.is_file():
            with open(embed_cfg_path, "r", encoding="utf-8", errors="replace") as f:
                embed_cfg = json.load(f)
        backend_name = embed_cfg.get("backend", "zhipu_embedding3")
        backend_section = embed_cfg.get(backend_name)
        backend_config = backend_section if isinstance(backend_section, dict) else embed_cfg.copy()
        if embed_api_key:
            backend_config = {**backend_config, "api_key": embed_api_key}
        backend = get_backend(backend_name, backend_config)

        chunk_paths = _embed_chunk_paths(chunk_dir)
        for jpath in chunk_paths:
            with open(jpath, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if not _is_chunks_json(data):
                continue
            embed_chunks(data, backend, overwrite=True)
            with open(jpath, "w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # Step 5: FAISS
        index_dir = out_base / "indexes"
        index_dir.mkdir(parents=True, exist_ok=True)
        faiss_path = index_dir / "papers.faiss"
        vectors = load_embeddings_from_folder(chunk_dir)
        index = build_faiss_index(vectors, use_gpu=use_gpu_faiss)
        faiss.write_index(index, str(faiss_path))

        # Subcollection mapping for step 6 (pdf stem -> folder path relative to papers root)
        mapping_path = index_dir / "subcollection_mapping.json"
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(subcollection_mapping, f, indent=0)

        # Step 6: SQLite
        db_path = index_dir / "chunks.db"
        store_metadata_from_folder(chunk_dir, db_path, subcollection_mapping_path=mapping_path)

        figures_root = figures_out / "cropped_figures" if pdffigures2_dir and (figures_out / "cropped_figures").is_dir() else None

        def _rel_or_abs(p: Path) -> str:
            try:
                return str(p.relative_to(_ROOT))
            except ValueError:
                return str(p)

        return {
            "faiss_index": _rel_or_abs(faiss_path),
            "sqlite_db": _rel_or_abs(db_path),
            "figures_root": _rel_or_abs(figures_root) if figures_root else None,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
