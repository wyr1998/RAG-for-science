"""
Post-process GROBID output JSON: remove spurious figure/table entries and make
IDs consistent with the 'head' field (e.g. head "Fig. 3" -> id "fig_3").
"""

import json
import shutil
import re
from pathlib import Path


# Minimum length for a plausible caption (characters)
MIN_DESC_LENGTH = 40

def _is_spurious(entry: dict) -> bool:
    """Return True if this figure/table entry is likely a GROBID mistake."""
    head = (entry.get("head") or "").strip()
    label = (entry.get("label") or "").strip()
    desc = (entry.get("desc") or "").strip()
    etype = (entry.get("type") or "figure").lower()

    # No head and no label -> likely spurious
    if not head and not label:
        return True

    # Very short description that doesn't look like a caption
    if len(desc) < MIN_DESC_LENGTH:
        if not head:
            return True
        # Allow short desc only if it looks like "Fig. 1" or "Table 1"
        if not re.search(r"(Fig\.|Figure|Table)\s*\d", desc, re.IGNORECASE):
            return True

    # Axis-label-like: e.g. "dist. to Reb1 dist. to BamHI linker"
    if re.match(r"^[\w\s\.]+(dist\.?\s*to|linker)[\w\s\.]*$", desc, re.IGNORECASE) and len(desc) < 80:
        return True

    return False


def _number_from_head(head: str) -> int | None:
    """Extract figure/table number from head, e.g. 'Fig. 3' -> 3, 'Table 1' -> 1."""
    if not head:
        return None
    m = re.search(r"(?:Fig\.?|Figure|Table)\s*(\d+)", head, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _id_from_head(entry: dict, index_by_type: dict) -> str:
    """Build id from head so it is consistent (e.g. Fig. 3 -> fig_3)."""
    head = (entry.get("head") or "").strip()
    etype = (entry.get("type") or "figure").lower()
    prefix = "fig" if etype == "figure" else "table"

    num = _number_from_head(head)
    if num is not None:
        candidate = f"{prefix}_{num}"
        # Avoid duplicate ids: if we already used this id, append _2, _3, ...
        if candidate not in index_by_type:
            index_by_type[candidate] = True
            return candidate
        k = 2
        while f"{candidate}_{k}" in index_by_type:
            k += 1
        candidate = f"{candidate}_{k}"
        index_by_type[candidate] = True
        return candidate
    # Fallback: no number in head, use prefix + index
    idx = len([k for k in index_by_type if k.startswith(prefix)])
    fallback = f"{prefix}_{idx + 1}"
    index_by_type[fallback] = True
    return fallback


def postprocess_figures_and_tables(data: dict) -> dict:
    """Filter spurious entries and set ids from head. Modifies data in place."""
    if "figures_and_tables" not in data:
        return data

    kept = []
    index_by_type = {}

    for entry in list(data["figures_and_tables"]):
        if _is_spurious(entry):
            continue
        entry = dict(entry)
        entry["id"] = _id_from_head(entry, index_by_type)
        # Keep label consistent with head if head has a number
        num = _number_from_head(entry.get("head") or "")
        if num is not None:
            entry["label"] = str(num)
        kept.append(entry)

    data["figures_and_tables"] = kept
    return data


def _is_grobid_json(data: dict) -> bool:
    """True if this looks like GROBID output (has body_text list)."""
    return isinstance(data.get("body_text"), list)


def _grobid_json_paths(folder: Path) -> list[Path]:
    """Return sorted paths to JSON files in folder that are GROBID output (skip config, stats, etc.)."""
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


def run_postprocess(
    input_path: str | Path,
    output_path: str | Path | None = None,
    no_backup: bool = False,
) -> None:
    """Run postprocess on a GROBID JSON file or folder. In-place if output_path is None."""
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
            postprocess_figures_and_tables(data)
            out_path = out_dir / jpath.name if out_dir.is_dir() else out_dir
            if out_path == jpath and not no_backup:
                shutil.copy2(jpath, jpath.with_suffix(jpath.suffix + ".bak"))
                print(f"Backup: {jpath.with_suffix(jpath.suffix + '.bak')}")
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Written: {out_path}  (figures_and_tables: {len(data.get('figures_and_tables', []))})")
        print(f"Processed {len(json_paths)} file(s).")
        return

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    out_path = Path(output_path).resolve() if output_path else path

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    postprocess_figures_and_tables(data)

    if out_path == path and not no_backup:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        print(f"Backup: {path.with_suffix(path.suffix + '.bak')}")

    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Written: {out_path}")
    print(f"figures_and_tables count: {len(data.get('figures_and_tables', []))}")
