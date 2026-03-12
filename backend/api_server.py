"""
FastAPI server for the knowledge base.

Exposes a simple HTTP API for querying the existing FAISS+SQLite+LLM pipeline.

Run (from project root):
    uvicorn api_server:app --reload

Requirements:
    pip install fastapi uvicorn
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import numpy as np
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

# Ensure project root on sys.path so backend.* modules can be imported.
# When frozen (PyInstaller), ROOT = directory containing the executable (for data paths);
# the launcher sets sys.path to include the bundle (_MEIPASS).
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from step7_query.query_pipeline import run_retrieval  # type: ignore
from step8_llm.llm_answer import answer_question  # type: ignore

try:
    from pipeline_runner import run_index_pipeline  # type: ignore
except ImportError:
    run_index_pipeline = None

from step1_grobid.process_pdfs import process_pdfs  # type: ignore
from step1_grobid.postprocess_grobid_json import run_postprocess  # type: ignore
from step1_grobid.add_token_counts import (  # type: ignore
    run_add_token_counts,
    DEFAULT_ENCODING,
)
from step1_grobid.add_paragraph_figure_refs import run_add_figure_refs  # type: ignore
from step1_grobid.chunk_papers import run_chunk_papers  # type: ignore
from step5_faiss.incremental_add import (  # type: ignore
    _embed_new_chunks,
    _append_to_faiss,
    _append_to_sqlite,
)
from step4_embeddings.embedding_interface import get_backend  # type: ignore
from grobid_docker import ensure_grobid_container_running


class IndexRequest(BaseModel):
    papers_folder: str
    output_base: str | None = None
    embed_api_key: str | None = None
    auto_figures: bool = True


class IndexResponse(BaseModel):
    faiss_index: str
    sqlite_db: str
    figures_root: str | None


class QARequest(BaseModel):
    query: str
    top_k: int | None = 50
    paper_top_k: int | None = 5
    llm_chunks_per_paper: int | None = 3
    faiss_index: str = "backend/indexes/papers.faiss"
    sqlite_db: str = "backend/indexes/chunks.db"
    embed_backend: str = "zhipu_embedding3"
    # Configs now live under backend/, so use backend-relative defaults
    embed_config: str = "backend/step4_embeddings/config.json"
    llm_config: str = "backend/step8_llm/config.json"
    # Root folder that contains cropped figures. figure_paths in DB are relative to this.
    figures_root: str = "backend/figures_output/cropped_figures"
    embed_api_key: str | None = None
    llm_api_key: str | None = None


class QAResponse(BaseModel):
    answer: str
    retrieval: Dict[str, Any]


app = FastAPI(title="Knowledge Base API", version="0.1.0")

# Allow both the React dev server and packaged desktop app to call this API.
# For a local desktop app we can safely allow all origins.
ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: For local desktop-app usage we allow the client to choose a figures root.
# We keep a process-global current root updated on each /qa call.
# If you later need multi-user concurrency, switch to encoding the root into the figure URL.
_FIGURES_ROOT_LOCK = threading.Lock()
_CURRENT_FIGURES_ROOT: Path | None = None


def _safe_join(base: Path, rel: str) -> Path:
    """Join base + rel and prevent path traversal."""
    full = (base / Path(rel)).resolve()
    base_resolved = base.resolve()
    if base_resolved not in full.parents and full != base_resolved:
        raise ValueError("Path traversal detected")
    return full


def _resolve_papers_root(papers_root: str) -> Path:
    p = Path(papers_root)
    root = p.resolve() if p.is_absolute() else (ROOT / p).resolve()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"papers_root is not a directory: {root}")
    return root


def _validate_rel_subpath(rel: str) -> str:
    """
    Validate a user-provided relative folder path like 'ML/2024'.
    Disallow absolute paths, drive letters, and path traversal.
    """
    if rel is None:
        return ""
    rel = str(rel).strip().replace("\\", "/").strip("/")
    if rel == "":
        return ""
    p = Path(rel)
    if p.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be relative")
    if p.drive:
        raise HTTPException(status_code=400, detail="Drive letters are not allowed")
    if any(part in ("..", "") for part in p.parts):
        raise HTTPException(status_code=400, detail="Invalid path")
    return rel


def _list_subfolders(root: Path) -> list[str]:
    out: list[str] = []
    for d in root.rglob("*"):
        if d.is_dir():
            rel = d.relative_to(root).as_posix()
            if rel:
                out.append(rel)
    out.sort()
    return out


def _list_pdfs_in_folder(root: Path, subcollection_path: str) -> list[dict[str, str]]:
    folder = root if subcollection_path == "" else _safe_join(root, subcollection_path)
    if not folder.is_dir():
        return []
    pdfs: list[dict[str, str]] = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if p.is_file() and p.suffix.lower() == ".pdf":
            rel = p.relative_to(root).as_posix()
            title = p.stem
            pdfs.append({"title": title, "rel_path": rel, "file_name": p.name})
    return pdfs


class PapersRootRequest(BaseModel):
    papers_root: str


class SubcollectionCreateRequest(BaseModel):
    papers_root: str
    subcollection_path: str


class SubcollectionRenameRequest(BaseModel):
    papers_root: str
    subcollection_path: str
    new_subcollection_path: str


class SubcollectionDeleteRequest(BaseModel):
    papers_root: str
    subcollection_path: str


class PaperMoveRequest(BaseModel):
    papers_root: str
    source_rel_path: str
    target_subcollection_path: str


class PaperDeleteRequest(BaseModel):
    papers_root: str
    rel_path: str


class AddPaperRequest(BaseModel):
    papers_root: str
    external_path: str
    target_subcollection_path: str = ""
    faiss_index: str
    sqlite_db: str
    embed_backend: str = "zhipu_embedding3"
    embed_config: str = "backend/step4_embeddings/config.json"
    embed_api_key: str | None = None


@app.get("/figures/{rel_path:path}")
def get_figure(rel_path: str):
    """
    Serve a cropped figure image.
    rel_path example: Rulerelements/Rulerelements_page03_figure1.png
    """
    with _FIGURES_ROOT_LOCK:
        base = _CURRENT_FIGURES_ROOT
    if base is None:
        root_setting = os.environ.get("FIGURES_ROOT") or "backend_output/cropped_figures"
        base = Path(root_setting)
        base = base if base.is_absolute() else (ROOT / base)
    try:
        path = _safe_join(base, rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid figure path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Figure not found: {rel_path}")
    return FileResponse(str(path))


def _add_figure_urls(retrieval_output: Dict[str, Any]) -> Dict[str, Any]:
    """Add figure_urls to chunks and paper.top_chunks based on figure_paths."""
    def to_url(p: str) -> str:
        p2 = str(p).replace("\\", "/")
        return f"http://localhost:8000/figures/{p2}"

    chunks = retrieval_output.get("chunks") or []
    if isinstance(chunks, list):
        for ch in chunks:
            fps = ch.get("figure_paths") or []
            ch["figure_urls"] = [to_url(x) for x in fps]

    papers = retrieval_output.get("papers") or []
    if isinstance(papers, list):
        for p in papers:
            tcs = p.get("top_chunks") or []
            if not isinstance(tcs, list):
                continue
            for tc in tcs:
                fps = tc.get("figure_paths") or []
                tc["figure_urls"] = [to_url(x) for x in fps]

    return retrieval_output


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.options("/index")
def options_index(request: Request) -> Response:
    """
    Explicit OPTIONS handler to make sure browsers receive CORS headers
    during preflight checks for /index.
    """
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": request.headers.get(
            "access-control-request-headers", "*"
        ),
    }
    return Response(status_code=200, headers=headers)


@app.post("/index", response_model=IndexResponse)
def index_papers(request: IndexRequest) -> IndexResponse:
    """
    Run the full pipeline on papers_folder (PDFs discovered recursively).
    Returns paths to the created FAISS index, SQLite DB, and figures root.
    """
    if run_index_pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline runner not available")
    path = Path(request.papers_folder)
    papers_folder_resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    pdffigures2_override = None
    if request.auto_figures:
        env_pdffigures2 = os.environ.get("PDFFIGURES2_DIR")
        if env_pdffigures2:
            env_path = Path(env_pdffigures2).resolve()
            if env_path.is_dir():
                pdffigures2_override = env_path
        if pdffigures2_override is None:
            default_pdffigures2 = (ROOT / "backend" / "pdffigures2").resolve()
            if default_pdffigures2.is_dir():
                pdffigures2_override = default_pdffigures2
    # If caller did not provide an explicit output_base, use a fixed
    # absolute path under ROOT so paths are stable in dev and packaged app.
    output_base = request.output_base or str((ROOT / "backend_output" / "paper").resolve())
    try:
        result = run_index_pipeline(
            papers_folder=papers_folder_resolved,
            output_base=output_base,
            embed_api_key=request.embed_api_key,
            pdffigures2_dir_override=pdffigures2_override,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return IndexResponse(
        faiss_index=result["faiss_index"],
        sqlite_db=result["sqlite_db"],
        figures_root=result.get("figures_root"),
    )


@app.get("/papers")
def list_papers(sqlite_db: str = "backend/indexes/chunks.db") -> Dict[str, Any]:
    """
    Return distinct paper titles (and file_name) from the chunks SQLite DB.
    Used by the frontend to show the list of papers in the knowledge base.
    """
    def _resolve(p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else ROOT / path

    db_path = _resolve(sqlite_db)
    if not db_path.is_file():
        return {"papers": []}

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT DISTINCT title, file_name, subcollection_path
                FROM chunks
                WHERE title IS NOT NULL AND title != ''
                ORDER BY title
                """
            )
            rows = cur.fetchall()
            papers = [
                {"title": row[0] or "(untitled)", "file_name": row[1] or "", "subcollection_path": row[2] or ""}
                for row in rows
            ]
        except sqlite3.OperationalError:
            cur.execute(
                """
                SELECT DISTINCT title, file_name
                FROM chunks
                WHERE title IS NOT NULL AND title != ''
                ORDER BY title
                """
            )
            rows = cur.fetchall()
            papers = [
                {"title": row[0] or "(untitled)", "file_name": row[1] or "", "subcollection_path": ""}
                for row in rows
            ]
        return {"papers": papers}
    finally:
        conn.close()


@app.get("/papers_tree")
def papers_tree(papers_root: str) -> Dict[str, Any]:
    root = _resolve_papers_root(papers_root)
    subcollections = [""] + _list_subfolders(root)
    return {"subcollections": subcollections}


@app.get("/papers_fs")
def papers_fs(papers_root: str, subcollection_path: str = "") -> Dict[str, Any]:
    root = _resolve_papers_root(papers_root)
    rel = _validate_rel_subpath(subcollection_path)
    return {"papers": _list_pdfs_in_folder(root, rel)}


@app.post("/subcollections/create")
def create_subcollection(request: SubcollectionCreateRequest) -> Dict[str, Any]:
    root = _resolve_papers_root(request.papers_root)
    rel = _validate_rel_subpath(request.subcollection_path)
    if rel == "":
        raise HTTPException(status_code=400, detail="Cannot create root")
    path = _safe_join(root, rel)
    path.mkdir(parents=True, exist_ok=False)
    return {"ok": True}


@app.post("/subcollections/rename")
def rename_subcollection(request: SubcollectionRenameRequest) -> Dict[str, Any]:
    root = _resolve_papers_root(request.papers_root)
    old_rel = _validate_rel_subpath(request.subcollection_path)
    new_rel = _validate_rel_subpath(request.new_subcollection_path)
    if old_rel == "" or new_rel == "":
        raise HTTPException(status_code=400, detail="Cannot rename root")
    old_path = _safe_join(root, old_rel)
    new_path = _safe_join(root, new_rel)
    if not old_path.is_dir():
        raise HTTPException(status_code=404, detail="Subcollection not found")
    if new_path.exists():
        raise HTTPException(status_code=400, detail="Target already exists")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)
    return {"ok": True}


@app.post("/subcollections/delete")
def delete_subcollection(request: SubcollectionDeleteRequest) -> Dict[str, Any]:
    root = _resolve_papers_root(request.papers_root)
    rel = _validate_rel_subpath(request.subcollection_path)
    if rel == "":
        raise HTTPException(status_code=400, detail="Cannot delete root")
    path = _safe_join(root, rel)
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Subcollection not found")
    try:
        next(path.iterdir())
        raise HTTPException(status_code=400, detail="Cannot delete non-empty folder")
    except StopIteration:
        pass
    path.rmdir()
    return {"ok": True}


@app.post("/papers/move")
def move_paper(request: PaperMoveRequest) -> Dict[str, Any]:
    root = _resolve_papers_root(request.papers_root)
    src_rel = _validate_rel_subpath(request.source_rel_path)
    if src_rel == "":
        raise HTTPException(status_code=400, detail="Invalid source")
    src = _safe_join(root, src_rel)
    if not src.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")
    if src.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files can be moved")
    tgt_rel = _validate_rel_subpath(request.target_subcollection_path)
    tgt_dir = root if tgt_rel == "" else _safe_join(root, tgt_rel)
    if not tgt_dir.is_dir():
        raise HTTPException(status_code=404, detail="Target subcollection not found")
    dst = (tgt_dir / src.name).resolve()
    if tgt_dir.resolve() not in dst.parents and dst != tgt_dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid target path")
    if dst.exists():
        raise HTTPException(status_code=400, detail="A file with the same name already exists in target")
    src.rename(dst)
    return {"ok": True, "new_rel_path": dst.relative_to(root).as_posix()}


@app.post("/papers/delete")
def delete_paper(request: PaperDeleteRequest) -> Dict[str, Any]:
    root = _resolve_papers_root(request.papers_root)
    rel = _validate_rel_subpath(request.rel_path)
    if rel == "":
        raise HTTPException(status_code=400, detail="Invalid path")
    path = _safe_join(root, rel)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files can be deleted")
    path.unlink()
    return {"ok": True}


@app.post("/papers/add_and_index")
def add_and_index_paper(request: AddPaperRequest) -> Dict[str, Any]:
    """
    Copy an external PDF into the papers_root/target_subcollection folder and
    incrementally append its chunks to the existing FAISS index and SQLite DB.
    """
    root = _resolve_papers_root(request.papers_root)
    rel_sub = _validate_rel_subpath(request.target_subcollection_path)
    target_dir = root if rel_sub == "" else _safe_join(root, rel_sub)
    target_dir.mkdir(parents=True, exist_ok=True)

    src = Path(request.external_path).expanduser().resolve()
    if not src.is_file():
        raise HTTPException(status_code=404, detail=f"Source file not found: {src}")
    if src.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    dst = target_dir / src.name
    if dst.exists():
        raise HTTPException(status_code=400, detail="File already exists in target folder")
    shutil.copy2(src, dst)
    rel_pdf_path = dst.relative_to(root).as_posix()

    # Resolve existing FAISS index and SQLite DB
    def _resolve_index_path(p: str) -> Path:
        path = Path(p)
        return path.resolve() if path.is_absolute() else (ROOT / p).resolve()

    faiss_index_path = _resolve_index_path(request.faiss_index)
    sqlite_db_path = _resolve_index_path(request.sqlite_db)
    if not faiss_index_path.is_file() or not sqlite_db_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="Existing FAISS index and SQLite DB are required. Run 'Index papers' once first.",
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="kb_add_paper_"))
    try:
        # Ensure GROBID is available (Docker container auto-start)
        try:
            ensure_grobid_container_running()
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        # Step 1: GROBID + postprocess + token counts + figure refs + chunking for this single PDF
        # Use a temp input dir containing only this PDF so we don't reprocess neighbors.
        pdf_input_dir = temp_dir / "pdf_input"
        pdf_input_dir.mkdir(parents=True, exist_ok=True)
        single_pdf_path = pdf_input_dir / dst.name
        try:
            single_pdf_path.symlink_to(dst)
        except OSError:
            shutil.copy2(dst, single_pdf_path)

        grobid_out = temp_dir / "grobid_output"
        step1_config = ROOT / "backend" / "step1_grobid" / "config.json"
        if getattr(sys, "frozen", False) and not step1_config.is_file():
            step1_config = Path(sys._MEIPASS) / "step1_grobid" / "config.json"
        if not step1_config.is_file():
            step1_config = Path("backend/step1_grobid/config.json")
        if not step1_config.is_file():
            step1_config = "config.json"

        process_pdfs(
            input_path=pdf_input_dir,
            output_path=grobid_out,
            config_path=str(step1_config),
            n_concurrent=1,
            json_output=True,
            markdown_output=False,
        )
        run_postprocess(grobid_out, output_path=None, no_backup=True)
        run_add_token_counts(grobid_out, output_path=None, encoding_name=DEFAULT_ENCODING, no_backup=True)
        run_add_figure_refs(grobid_out, output_path=None, no_backup=True)
        chunk_dir = grobid_out / "chunk"
        run_chunk_papers(grobid_out, output_path=chunk_dir)

        chunk_files = sorted(chunk_dir.glob("*_chunks.json"))
        if not chunk_files:
            raise HTTPException(status_code=500, detail="No chunks JSON produced for new paper")
        chunks_path = chunk_files[0]

        with open(chunks_path, "r", encoding="utf-8", errors="replace") as f:
            chunks = json.load(f)
        if not isinstance(chunks, list):
            raise HTTPException(status_code=500, detail="Chunks JSON has unexpected format")

        # Embed new chunks
        embed_cfg_path = Path(request.embed_config)
        if not embed_cfg_path.is_absolute():
            embed_cfg_path = (ROOT / embed_cfg_path).resolve()
        embed_cfg: dict = {}
        if embed_cfg_path.is_file():
            with open(embed_cfg_path, "r", encoding="utf-8", errors="replace") as f:
                embed_cfg = json.load(f)
        backend_name = request.embed_backend
        backend_section = embed_cfg.get(backend_name)
        backend_config = backend_section if isinstance(backend_section, dict) else embed_cfg.copy()
        if request.embed_api_key:
            backend_config = {**backend_config, "api_key": request.embed_api_key}
        backend = get_backend(backend_name, backend_config)
        _embed_new_chunks(chunks, backend)
        with open(chunks_path, "w", encoding="utf-8", errors="replace") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        vectors_list = [ch["embedding"] for ch in chunks if ch.get("embedding")]
        if not vectors_list:
            raise HTTPException(status_code=500, detail="No embeddings produced for new paper")
        vectors = np.asarray(vectors_list, dtype="float32")
        if vectors.ndim != 2:
            raise HTTPException(status_code=500, detail=f"Embeddings array must be 2D, got shape {vectors.shape}")

        start_id = _append_to_faiss(faiss_index_path, vectors)
        _append_to_sqlite(sqlite_db_path, chunks, start_id, paper_path=dst)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "ok": True,
        "rel_path": rel_pdf_path,
        "faiss_index": str(faiss_index_path.relative_to(ROOT) if ROOT in faiss_index_path.parents else faiss_index_path),
        "sqlite_db": str(sqlite_db_path.relative_to(ROOT) if ROOT in sqlite_db_path.parents else sqlite_db_path),
    }


@app.post("/ask", response_model=QAResponse)
def ask(request: QARequest) -> QAResponse:
    """Alias for /qa (used by the frontend)."""
    return qa(request)


def _load_embed_config_for_qa(embed_config_path: str, embed_backend: str, embed_api_key: str | None) -> str | dict:
    """Load embed config from path; if embed_api_key is set, return merged backend section dict."""
    path = Path(embed_config_path).resolve()
    if not path.is_file():
        return embed_config_path
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        cfg = json.load(f)
    section = cfg.get(embed_backend)
    config = dict(section) if isinstance(section, dict) else {}
    if embed_api_key:
        config["api_key"] = embed_api_key
        return config
    return embed_config_path


@app.post("/qa", response_model=QAResponse)
def qa(request: QARequest) -> QAResponse:
    """
    Run retrieval + LLM answer.

    Assumes FAISS index and SQLite DB already exist:
      - FAISS: indexes/papers.faiss (or request.faiss_index)
      - SQLite: indexes/chunks.db (or request.sqlite_db)
    """
    # Resolve paths relative to project root if not absolute
    def _resolve(p: str) -> str:
        path = Path(p)
        return str(path if path.is_absolute() else ROOT / p)

    faiss_index = _resolve(request.faiss_index)
    sqlite_db = _resolve(request.sqlite_db)
    embed_config_path = _resolve(request.embed_config)
    llm_config = _resolve(request.llm_config)
    figures_root = _resolve(request.figures_root)

    # Update process-global figures root for /figures serving
    global _CURRENT_FIGURES_ROOT
    with _FIGURES_ROOT_LOCK:
        _CURRENT_FIGURES_ROOT = Path(figures_root)

    embed_config = _load_embed_config_for_qa(
        embed_config_path, request.embed_backend, request.embed_api_key
    )

    # Build args namespace for run_retrieval
    retrieval_args = SimpleNamespace(
        query=request.query,
        faiss_index=faiss_index,
        sqlite_db=sqlite_db,
        backend=request.embed_backend,
        config=embed_config,
        top_k=request.top_k or 50,
        paper_aggregate=True,
        paper_top_k=request.paper_top_k or 5,
        llm_chunks_per_paper=request.llm_chunks_per_paper or 3,
    )

    retrieval_output = run_retrieval(retrieval_args)
    llm_context = retrieval_output.get("llm_context") or []

    llm_overrides = None
    if request.llm_api_key:
        from step8_llm.llm_answer import load_llm_config  # type: ignore
        llm_cfg = load_llm_config(llm_config)
        backend_name = llm_cfg.get("backend", "zhipu")
        llm_overrides = {backend_name: {"api_key": request.llm_api_key}}

    answer = answer_question(
        request.query,
        llm_context,
        config_path=llm_config,
        config_overrides=llm_overrides,
    )
    retrieval_output = _add_figure_urls(retrieval_output)
    return QAResponse(answer=answer, retrieval=retrieval_output)

