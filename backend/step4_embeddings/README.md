# Step 4: Embeddings

Embed chunk text with a **pluggable backend** so you can switch APIs (Zhipu Embedding-3, OpenAI, etc.) without changing pipeline code.

## Interface

- **`embedding_interface.py`** — Protocol `EmbeddingBackend`: `embed_texts(texts: list[str]) -> list[list[float]]`, `dimension`, `name`. Register new backends with `@register_backend("name")`.
- **`get_backend(name, config)`** — Returns an instance; config is passed as `**kwargs` to the backend constructor.

## Default backend: Zhipu Embedding-3

- **`backends/zhipu_embedding3.py`** — Uses `zhipuai` SDK; model `embedding-3`, configurable `dimensions` (default 1024).
- **API key:** Set env `ZHIPUAI_API_KEY` or put `api_key` in config (avoid committing secrets).

## Usage

```bash
# From project root
pip install zhipuai

# Single file (default: overwrite; use -o to write elsewhere)
python step4_embeddings/embed_chunks.py path/to/Rulerelements_chunks.json

# Folder: all *_chunks.json in directory
python step4_embeddings/embed_chunks.py path/to/chunk_folder -o path/to/out_dir

# Use config file (backend options: api_key, dimensions, model)
python step4_embeddings/embed_chunks.py path/to/chunks.json --config step4_embeddings/config.json

# Skip chunks that already have "embedding"
python step4_embeddings/embed_chunks.py path/to/chunks.json --no-overwrite
```

Config (e.g. `config.json`) can contain top-level `backend` and a key matching the backend name with its options:

```json
{
  "backend": "zhipu_embedding3",
  "zhipu_embedding3": {
    "model": "embedding-3",
    "dimensions": 1024
  }
}
```

If you pass `--config`, that file is used. Otherwise the script looks for `step4_embeddings/config.json`. Backend is still selected by `--backend`; config is merged into the backend constructor.

## Adding another backend

1. Implement a class with `embed_texts(texts) -> list[list[float]]`, `dimension` (property), `name` (property).
2. Decorate with `@register_backend("my_backend")` (in `embedding_interface.py` the decorator is defined).
3. Import the module in `step4_embeddings/embed_chunks.py` (e.g. add `from step4_embeddings.backends.my_backend import MyBackend` or keep the `from step4_embeddings.backends import *` so that any new backend in `backends/__init__.py` is registered).
4. Run with `--backend my_backend` and pass options via `--config`.

## Output

Each chunk gets an **`embedding`** field: `list[float]` of length `backend.dimension`. Existing fields (`chunk_id`, `section`, `text`, `figure_refs`, `figure_paths`, etc.) are unchanged.
