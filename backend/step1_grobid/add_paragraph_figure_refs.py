"""
Add figure_ids to each paragraph in GROBID output JSON.
Detects main-figure references (e.g. Fig. 1, Figure 2) and excludes supplementary
(Supplementary Fig., Suppl. Fig., Fig. S1, etc.).
"""

import json
import re
import shutil
from pathlib import Path

# Main figure: "Fig. 1", "Fig. 1a", "Figure 2b", "Figs. 1c, d"
# (?!S) excludes "Fig. S1" (supplementary)
MAIN_FIGURE_PATTERN = re.compile(
    r"\b(?:Fig\.?|Figures?)\s*(?!S)(\d+)",
    re.IGNORECASE,
)

# Supplementary patterns to mask so we don't count them (replaced with space)
SUPPLEMENTARY_PATTERNS = [
    re.compile(r"Supplementary\s+(?:Fig\.?|Figure)\s*S?\d+[a-z]*(?:\s*[a-z])?", re.IGNORECASE),
    re.compile(r"Suppl\.?\s*(?:Fig\.?|Figure)\s*S?\d+[a-z]*(?:\s*[a-z])?", re.IGNORECASE),
    re.compile(r"(?:Fig\.?|Figure)\s*S\d+[a-z]*", re.IGNORECASE),  # Fig. S1, Fig. S2a
]


def _mask_supplementary_refs(text: str) -> str:
    """Replace supplementary figure mentions with space so main-figure regex won't match them."""
    if not text:
        return ""
    out = text
    for pat in SUPPLEMENTARY_PATTERNS:
        out = pat.sub(" ", out)
    return out


def extract_main_figure_ids(text: str) -> list[str]:
    """
    Extract main figure numbers from text (no supplementary).
    Returns sorted list of figure IDs as "fig_1", "fig_2", etc.
    """
    if not text or not isinstance(text, str):
        return []
    masked = _mask_supplementary_refs(text)
    numbers = sorted({int(m.group(1)) for m in MAIN_FIGURE_PATTERN.finditer(masked)})
    return [f"fig_{n}" for n in numbers]


def add_figure_ids_to_grobid_json(data: dict) -> dict:
    """
    Add "figure_ids" (list of main-figure ids, no supplementary) to each
    body_text paragraph and each biblio.abstract item. Modifies data in place.
    """
    # Abstract
    if "biblio" in data and isinstance(data["biblio"].get("abstract"), list):
        for item in data["biblio"]["abstract"]:
            if isinstance(item, dict) and "text" in item:
                item["figure_ids"] = extract_main_figure_ids(item.get("text"))

    # Body text
    if "body_text" in data and isinstance(data["body_text"], list):
        for item in data["body_text"]:
            if isinstance(item, dict) and "text" in item:
                item["figure_ids"] = extract_main_figure_ids(item.get("text"))

    return data


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


def run_add_figure_refs(
    input_path: str | Path,
    output_path: str | Path | None = None,
    no_backup: bool = False,
) -> None:
    """Add figure_ids to GROBID JSON file or folder. In-place if output_path is None."""
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
            add_figure_ids_to_grobid_json(data)
            out_path = out_dir / jpath.name if out_dir.is_dir() else out_dir
            if out_path == jpath and not no_backup:
                shutil.copy2(jpath, jpath.with_suffix(jpath.suffix + ".bak"))
                print(f"Backup: {jpath.with_suffix(jpath.suffix + '.bak')}")
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            n_with = sum(1 for p in (data.get("body_text") or []) if p.get("figure_ids"))
            print(f"Written: {out_path}  (paragraphs with figure_ids: {n_with})")
        print(f"Processed {len(json_paths)} file(s).")
        return

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    add_figure_ids_to_grobid_json(data)

    out_path = Path(output_path).resolve() if output_path else path
    if out_path == path and not no_backup:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        print(f"Backup: {path.with_suffix(path.suffix + '.bak')}")

    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Written: {out_path}")
    n_with_figs = sum(1 for p in (data.get("body_text") or []) if p.get("figure_ids"))
    print(f"Paragraphs with at least one figure_id: {n_with_figs} / {len(data.get('body_text') or [])}")
