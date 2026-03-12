"""
Figure-aware chunking for GROBID-parsed papers.
Does not mix sections; respects MAX_TOKENS and figure boundaries via dominant_figure logic.
"""

import json
import re
from pathlib import Path

MAX_TOKENS = 800

# Extract figure number from "fig_1", "fig_2", etc.
FIG_ID_PATTERN = re.compile(r"fig_(\d+)", re.IGNORECASE)


def _figure_numbers_from_ids(figure_ids: list) -> set[int]:
    """Parse figure_ids (e.g. ["fig_1", "fig_2"]) into set of integers."""
    if not figure_ids:
        return set()
    out = set()
    for fid in figure_ids:
        if isinstance(fid, str):
            m = FIG_ID_PATTERN.search(fid)
            if m:
                out.add(int(m.group(1)))
        elif isinstance(fid, int):
            out.add(fid)
    return out


def _build_chunk(section: str, paragraphs: list[dict], section_counts: dict[str, int]) -> dict:
    """Build one chunk from paragraphs and increment section_counts for chunk_id."""
    norm = (section or "").strip().lower() or "main"
    idx = section_counts.get(norm, 0)
    section_counts[norm] = idx + 1

    text_parts = [p.get("text", "").strip() for p in paragraphs if p.get("text", "").strip()]
    text = "\n\n".join(text_parts)
    token_count = sum(int(p.get("token_count", 0)) for p in paragraphs)

    # Collect all figure_ids from paragraphs
    all_fig_ids: set[str] = set()
    for p in paragraphs:
        for fid in p.get("figure_ids") or []:
            if fid:
                all_fig_ids.add(str(fid) if not isinstance(fid, str) else fid)
    def _fig_sort_key(s: str) -> int:
        m = re.search(r"\d+", s or "")
        return int(m.group()) if m else 0

    figure_refs = sorted(all_fig_ids, key=_fig_sort_key)

    return {
        "chunk_id": f"{norm}_{idx}",
        "section": section,
        "text": text,
        "figure_refs": figure_refs,
        "token_count": token_count,
    }


def chunk_paragraphs(paragraphs: list[dict]) -> list[dict]:
    """
    Chunk paragraphs using figure-aware strategy.

    Input: list of dicts with section, text, token_count, figure_ids
    Output: list of chunks with chunk_id, section, text, figure_refs, token_count
    """
    if not paragraphs:
        return []

    chunks_out: list[dict] = []
    current_paras: list[dict] = []
    current_section: str = (paragraphs[0].get("section") or paragraphs[0].get("head_section") or "").strip()
    current_token_count = 0
    dominant_figure: int | None = None
    candidate_new_figure: int | None = None
    consecutive_new_figure_count: int = 0
    section_counts: dict[str, int] = {}

    def close_current_chunk() -> None:
        nonlocal current_paras, current_token_count, candidate_new_figure, consecutive_new_figure_count
        if not current_paras:
            return
        chunks_out.append(_build_chunk(current_section, current_paras, section_counts))
        current_paras = []
        current_token_count = 0
        candidate_new_figure = None
        consecutive_new_figure_count = 0

    for para in paragraphs:
        section = (para.get("section") or para.get("head_section") or "").strip()
        norm_section = (section or "main").lower()
        norm_current = (current_section or "main").lower()

        # Rule 1: Section change — do not mix sections
        if norm_section != norm_current:
            close_current_chunk()
            current_section = section
            dominant_figure = None
            candidate_new_figure = None
            consecutive_new_figure_count = 0

        fig_nums = _figure_numbers_from_ids(para.get("figure_ids") or [])

        # Rule A: Paragraph has no figure
        if not fig_nums:
            # Add to chunk; do not change dominant_figure
            pass

        # Rule B: dominant_figure is None and paragraph has figures
        elif dominant_figure is None:
            dominant_figure = min(fig_nums)

        # Rule C: Paragraph contains dominant_figure
        elif dominant_figure in fig_nums:
            candidate_new_figure = None
            consecutive_new_figure_count = 0

        # Rule D: Paragraph does NOT contain dominant_figure but has larger figure
        elif fig_nums:
            larger = [f for f in fig_nums if f > dominant_figure]
            new_fig = min(larger) if larger else None
            if new_fig is not None:
                if candidate_new_figure == new_fig:
                    consecutive_new_figure_count += 1
                else:
                    candidate_new_figure = new_fig
                    consecutive_new_figure_count = 1

                if consecutive_new_figure_count >= 2:
                    # Close chunk, start new, switch dominant
                    close_current_chunk()
                    current_section = section
                    dominant_figure = new_fig
                    candidate_new_figure = None
                    consecutive_new_figure_count = 0

        # Rule E: Smaller figure (backward ref) — add to chunk, no state change

        # Rule 5: Would exceed MAX_TOKENS
        if current_paras and (current_token_count + int(para.get("token_count", 0))) > MAX_TOKENS:
            close_current_chunk()
            current_section = section
            candidate_new_figure = None
            consecutive_new_figure_count = 0
            if fig_nums:
                dominant_figure = min(fig_nums)

        current_paras.append(para)
        current_token_count += int(para.get("token_count", 0))

    # Rule 6: Append final chunk
    close_current_chunk()

    return chunks_out


def _figure_caption_map(grobid_data: dict) -> dict[str, str]:
    """Build mapping fig_id -> caption/description text from figures_and_tables."""
    out: dict[str, str] = {}
    for item in grobid_data.get("figures_and_tables") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "figure":
            continue
        fig_id = item.get("id")
        if not fig_id:
            continue
        desc = (item.get("desc") or "").strip()
        if desc:
            out[str(fig_id)] = desc
    return out


def chunk_grobid_json(grobid_data: dict) -> list[dict]:
    """Build paragraph list from GROBID JSON and return enriched chunks."""
    body = grobid_data.get("body_text") or []
    paragraphs = []
    for item in body:
        paragraphs.append(
            {
                "section": item.get("head_section") or item.get("section") or "",
                "text": item.get("text") or "",
                "token_count": int(item.get("token_count", 0)),
                "figure_ids": item.get("figure_ids") or [],
            }
        )

    chunks = chunk_paragraphs(paragraphs)

    # Enrich each chunk with paper-level metadata and figure captions
    biblio = grobid_data.get("biblio") or {}
    doi = biblio.get("doi") or ""
    journal = biblio.get("journal") or ""
    publication_date = biblio.get("publication_date") or ""
    title = biblio.get("title") or ""

    fig_captions = _figure_caption_map(grobid_data)

    for ch in chunks:
        # Paper-level fields
        ch["doi"] = doi
        ch["journal"] = journal
        ch["publication_date"] = publication_date
        ch["title"] = title

        # Figure captions corresponding to figure_refs
        caps: list[str] = []
        for fid in ch.get("figure_refs") or []:
            cap = fig_captions.get(str(fid))
            if cap:
                caps.append(cap)
        ch["figure_captions"] = caps

    return chunks


def _is_grobid_json(data: dict) -> bool:
    """True if this looks like GROBID output (has body_text list)."""
    return isinstance(data.get("body_text"), list)


def _grobid_json_paths(folder: Path) -> list[Path]:
    """Return sorted paths to JSON files in folder that are GROBID output."""
    out = []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() != ".json":
            continue
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fp:
                data = json.load(fp)
            if _is_grobid_json(data):
                out.append(f)
        except Exception:
            continue
    return out


def run_chunk_papers(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> None:
    """Chunk GROBID JSON file or folder. Writes <stem>_chunks.json per file. If output_path is None, writes to input dir (folder) or parent (file)."""
    path = Path(input_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")

    if path.is_dir():
        json_paths = _grobid_json_paths(path)
        if not json_paths:
            print("No GROBID JSON files found in folder.")
            return
        out_dir = Path(output_path).resolve() if output_path else path
        if output_path and not out_dir.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
        for jpath in json_paths:
            with open(jpath, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            chunks = chunk_grobid_json(data)
            out_path = out_dir / f"{jpath.stem}_chunks.json" if out_dir.is_dir() else out_dir
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
            print(f"Wrote {len(chunks)} chunks to {out_path}")
        print(f"Processed {len(json_paths)} file(s).")
        return

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    chunks = chunk_grobid_json(data)

    out_path = Path(output_path).resolve() if output_path else path.parent / f"{path.stem}_chunks.json"
    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(chunks)} chunks to {out_path}")
