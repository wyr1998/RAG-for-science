"""
Add tiktoken token counts to GROBID output JSON.
Adds a "token_count" field to each body_text paragraph, each abstract paragraph,
and each figure/table (for "desc" and "note").
"""

import json
import shutil
from pathlib import Path

try:
    import tiktoken
except ImportError:
    raise ImportError(
        "tiktoken not installed. Install it with:\n"
        "  conda activate knowledgebase\n"
        "  pip install tiktoken"
    )


# Default: OpenAI cl100k_base (GPT-4, GPT-3.5-turbo, embeddings)
DEFAULT_ENCODING = "cl100k_base"


def get_encoder(encoding_name: str = DEFAULT_ENCODING):
    """Return tiktoken encoder. Use encoding name (e.g. cl100k_base) or model name (e.g. gpt-4)."""
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception:
        # In some frozen/PyInstaller environments, tiktoken's full model/encoding
        # data may not be available. Fall back to model-based lookup, then to a
        # widely available encoding, and finally to a simple byte-based counter.
        try:
            return tiktoken.encoding_for_model(encoding_name)
        except Exception:
            try:
                # gpt2 encoding is usually available even when others are not.
                return tiktoken.get_encoding("gpt2")
            except Exception:
                class _ByteLengthEncoder:
                    def encode(self, text: str):
                        if not isinstance(text, str):
                            return b""
                        return text.encode("utf-8", errors="ignore")

                return _ByteLengthEncoder()


def count_tokens(text: str, encoder) -> int:
    if not text or not isinstance(text, str):
        return 0
    return len(encoder.encode(text))


def add_token_counts_to_grobid_json(
    data: dict,
    encoding_name: str = DEFAULT_ENCODING,
) -> dict:
    """
    Add "token_count" to each paragraph and text field in GROBID JSON.
    Modifies data in place and returns it.
    """
    encoder = get_encoder(encoding_name)
    total = 0

    # Abstract paragraphs
    if "biblio" in data and isinstance(data["biblio"].get("abstract"), list):
        for item in data["biblio"]["abstract"]:
            if isinstance(item, dict) and "text" in item:
                n = count_tokens(item["text"], encoder)
                item["token_count"] = n
                total += n

    # Body text paragraphs
    if "body_text" in data and isinstance(data["body_text"], list):
        for item in data["body_text"]:
            if isinstance(item, dict) and "text" in item:
                n = count_tokens(item["text"], encoder)
                item["token_count"] = n
                total += n

    # Figures and tables: count desc and note
    if "figures_and_tables" in data and isinstance(data["figures_and_tables"], list):
        for item in data["figures_and_tables"]:
            if not isinstance(item, dict):
                continue
            n_desc = count_tokens(item.get("desc"), encoder)
            n_note = count_tokens(item.get("note"), encoder)
            item["token_count"] = n_desc + n_note
            item["token_count_desc"] = n_desc
            item["token_count_note"] = n_note
            total += n_desc + n_note

    data["_token_count_total"] = total
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


def run_add_token_counts(
    input_path: str | Path,
    output_path: str | Path | None = None,
    encoding_name: str = DEFAULT_ENCODING,
    no_backup: bool = False,
) -> None:
    """Add token counts to GROBID JSON file or folder. In-place if output_path is None."""
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
            add_token_counts_to_grobid_json(data, encoding_name=encoding_name)
            out_path = out_dir / jpath.name if out_dir.is_dir() else out_dir
            if out_path == jpath and not no_backup:
                shutil.copy2(jpath, jpath.with_suffix(jpath.suffix + ".bak"))
                print(f"Backup: {jpath.with_suffix(jpath.suffix + '.bak')}")
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Written: {out_path}  (total tokens: {data.get('_token_count_total', 0)})")
        print(f"Processed {len(json_paths)} file(s).")
        return

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    add_token_counts_to_grobid_json(data, encoding_name=encoding_name)

    out_path = Path(output_path).resolve() if output_path else path
    if out_path == path and not no_backup:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        print(f"Backup: {path.with_suffix(path.suffix + '.bak')}")

    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Written: {out_path}")
    print(f"Total token count: {data.get('_token_count_total', 0)}")
    if "body_text" in data:
        n_par = len(data["body_text"])
        print(f"Body paragraphs: {n_par} (each has 'token_count')")
