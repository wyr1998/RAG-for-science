# Knowledge Base — Scientific Paper QA Pipeline

Build a searchable knowledge base from PDF papers: extract structure (GROBID), figures (PDFFigures2), chunk text, embed with a pluggable API, index with FAISS, store metadata in SQLite, and answer questions via retrieval + a configurable LLM.

---

## Overview

```
PDFs → [Step 1] GROBID (structure) → [Step 2] PDFFigures2 (figures) → [Step 3] Link figures to chunks
         ↓
      [Step 1] Chunk papers (figure-aware) → [Step 4] Embed chunks → [Step 5] FAISS index
                                                                     [Step 6] SQLite metadata
                                                                           ↓
      Query → [Step 7] Embed query → FAISS search → Paper aggregation → [Step 8] LLM answer
```

- **Steps 1–3:** Ingest PDFs, extract figures, produce chunks with `figure_refs` and `figure_paths`.
- **Steps 4–6:** Embed chunks (pluggable backend), build FAISS index and SQLite DB (aligned by `faiss_id`).
- **Steps 7–8:** Embed query, retrieve top chunks, aggregate by paper, build LLM context, call LLM (config-driven) and print the answer.

---

## Prerequisites

- **Python 3.10+** (e.g. Anaconda env `knowledgebase`)
- **Docker Desktop** — GROBID runs in a container (port 8070)
- **Optional:** Java + sbt — only needed for PDFFigures2 if you do not use the fat JAR or bundled JRE (see below).

Install core dependencies from project root:

```bash
pip install -r requirements.txt
pip install zhipuai PyMuPDF numpy
conda install -c conda-forge faiss-cpu   # Windows; use faiss-gpu on Linux if desired
```

### Running the backend with a bundled JRE (desktop app)

To let users run PDFFigures2 **without installing JDK or sbt**, bundle a JRE and use the launcher:

1. **Build the PDFFigures2 fat JAR** (once): run `sbt assembly` in `backend/pdffigures2/` (or use `backend/scripts/build_pdffigures2_jar.bat`). The JAR will be at `backend/pdffigures2/pdffigures2.jar` or under `target/scala-2.12/*assembly*.jar`.

2. **Bundle a JRE**: Download a portable JRE (e.g. [Adoptium](https://adoptium.net/)) for your target OS/arch and unpack it into a **`jre`** folder at the **app root** (the directory that contains `backend/` and the launcher). So the layout is:
   ```
   app_root/
   ├── jre/           ← unpacked JRE here (bin/java.exe or bin/java)
   ├── backend/
   │   ├── pdffigures2/
   │   │   └── pdffigures2.jar
   │   └── ...
   └── run_backend.bat
   ```

3. **Start the backend with the launcher**: From the project root, run **`run_backend.bat`**. It sets **`BUNDLED_JRE_DIR`** to `app_root\jre` when that folder exists, then starts the API server. The figure extractor will use the bundled JRE to run the PDFFigures2 JAR, so users need neither a system JDK nor sbt. Do **not** set `JAVA_HOME` or add the JRE to the system PATH so other applications are unaffected.

### Building the backend with PyInstaller

To build a single executable for the API server (e.g. for Tauri or a standalone desktop app). The spec bundles numpy/faiss and, when you build under Anaconda, the required MKL DLLs so the EXE runs on machines **without Anaconda**.

1. **Install PyInstaller** (from project root):
   ```bash
   pip install pyinstaller
   ```

2. **Build** (from project root):
   ```bash
   pyinstaller backend/backend.spec
   ```
   Output: `dist/backend.exe` (Windows) or `dist/backend` (Unix).

3. **Place data next to the executable** so the server can find PDFFigures2 and the JRE. Create this layout next to the EXE:
   ```
   dist/
     backend.exe
     backend/
       pdffigures2/
         pdffigures2.jar
       jdk-17.0.18+8-jre/
         bin/
           java.exe
         lib/
         ...
   ```
   Copy (or symlink) your existing `backend/pdffigures2/pdffigures2.jar` and `backend/jdk-17.0.18+8-jre/` into `dist/backend/`. Config files (`step1_grobid/config.json`, etc.) are bundled inside the EXE; you can override them by placing files at `dist/backend/step1_grobid/config.json` etc. if needed.

4. **Run**: From `dist/`, run `backend.exe`. It will set `BUNDLED_JRE_DIR` to `dist/backend/jdk-17.0.18+8-jre` automatically and start the API on `http://0.0.0.0:8000`.

---

## Quick Start (Answer a Question)

1. **Start GROBID** (Docker):

   ```powershell
   docker run -d --init -p 8070:8070 grobid/grobid:0.8.2-full
   ```

2. **Put your Zhipu API key** in config (or set `ZHIPUAI_API_KEY`):
   - `step4_embeddings/config.json` — `zhipu_embedding3.api_key` (for retrieval)
   - `step8_llm/config.json` — `zhipu.api_key` (for LLM)

3. **Run the full pipeline** (after you have already built the index once, see below):

   ```bash
   python step8_llm/llm_answer.py \
     --query "How do nucleosome arrays form chromatin domains?" \
     --faiss-index indexes/papers.faiss \
     --sqlite-db indexes/chunks.db
   ```

   Default configs: `--embed-config step4_embeddings/config.json`, `--llm-config step8_llm/config.json`. Override with `--embed-config` and `--llm-config` if needed.

---

## Pipeline Steps

### Step 1 — GROBID: Structure + Chunking

**1a. Process PDFs** (`step1_grobid/`)

- Send PDFs to GROBID; get TEI XML and JSON (CORD-19-like).
- Single file or folder.

```bash
python step1_grobid/process_pdfs.py path/to/paper.pdf
python step1_grobid/process_pdfs.py path/to/pdfs_folder -o output_folder
```

Config: `step1_grobid/config.json` → `grobid_server: http://localhost:8070`.

**1b. Postprocess, tokenize, figure refs, chunk**

Run in order on the GROBID JSON output (file or folder):

```bash
python step1_grobid/postprocess_grobid_json.py    grobid_output/
python step1_grobid/add_token_counts.py          grobid_output/
python step1_grobid/add_paragraph_figure_refs.py grobid_output/
python step1_grobid/chunk_papers.py              grobid_output/ -o grobid_output/chunk/
```

Chunks get: `chunk_id`, `section`, `text`, `figure_refs`, `token_count`, plus paper-level `doi`, `journal`, `publication_date`, `title`, and `figure_captions` for referenced figures.

---

### Step 2 — Figures (PDFFigures2 + crop)

- Extract figure metadata (coordinates) with PDFFigures2; correct 0-based → 1-based page numbers; crop figures with PyMuPDF.

See `step2_figures/README.md` for PDFFigures2 setup and commands (`extract_figures.py`, `crop_figures.py`).

---

### Step 3 — Link figures to chunks

- Add `figure_paths` to each chunk from `figure_refs` by scanning the cropped figure directory.

```bash
# Single file
python step3_link_figures/link_figures_to_chunks.py path/to/paper_chunks.json path/to/cropped_figures_dir --paper PaperStem

# Folder of *_chunks.json
python step3_link_figures/link_figures_to_chunks.py path/to/chunk_folder path/to/cropped_figures_parent -o path/to/out_dir
```

---

### Step 4 — Embed chunks

- Pluggable embedding backend (default: Zhipu Embedding-3). Writes an `embedding` field into each chunk.

```bash
python step4_embeddings/embed_chunks.py grobid_output/chunk/ -o chunk_embedding
```

Config: `step4_embeddings/config.json`; use `--config` and `--backend` to switch. See `step4_embeddings/README.md`.

---

### Step 5 — FAISS index

- Build a FAISS index from all chunk embeddings in a folder (same order as Step 6).

```bash
python step5_faiss/faiss_storage.py chunk_embedding indexes/papers.faiss --cpu-only
```

On Windows use `faiss-cpu`; script is `faiss_storage.py` (avoid naming a script `faiss.py` so it doesn’t shadow the `faiss` module).

---

### Step 6 — SQLite metadata

- Store chunk metadata in SQLite with `faiss_id` aligned to FAISS vector index.

```bash
python step6_sqlite/sqlite_storage.py chunk_embedding indexes/chunks.db
```

Use the **same** `chunk_embedding` folder as in Step 5 so that `faiss_id` matches the FAISS index.

---

### Step 7 — Query (retrieval only)

- Embed query, search FAISS, fetch metadata from SQLite, optionally aggregate by paper and build LLM context. Output is JSON.

```bash
python step7_query/query_pipeline.py \
  --query "Your question" \
  --faiss-index indexes/papers.faiss \
  --sqlite-db indexes/chunks.db \
  --top-k 50 --paper-aggregate --paper-top-k 5
```

---

### Step 8 — LLM answer

- **Programmatic:** `answer_question(query, llm_context, config_path=None)` in `step8_llm/llm_answer.py`; uses `step8_llm/config.json` by default.
- **CLI (retrieval + LLM in one go):**

```bash
python step8_llm/llm_answer.py \
  --query "Your question" \
  --faiss-index indexes/papers.faiss \
  --sqlite-db indexes/chunks.db \
  --embed-config step4_embeddings/config.json \
  --llm-config step8_llm/config.json
```

`--embed-config` and `--llm-config` default to `step4_embeddings/config.json` and `step8_llm/config.json` (resolved from project root). LLM backend and API key are set in the LLM config (e.g. `zhipu` with `api_key` or `api_key_env`).

---

## Config and API Keys

| Config file | Purpose |
|-------------|--------|
| `step1_grobid/config.json` | GROBID server URL |
| `step4_embeddings/config.json` | Embedding backend and options (e.g. `zhipu_embedding3` with `api_key`) |
| `step8_llm/config.json` | LLM backend and options (e.g. `zhipu` with `api_key` or `api_key_env`) |

- **Embedding:** Set `api_key` in the backend section of `step4_embeddings/config.json`, or set the env var named by `api_key_env` (e.g. `ZHIPUAI_API_KEY`).
- **LLM:** Set `api_key` in the backend section of `step8_llm/config.json`, or set the env var named by `api_key_env`. Do not put the key in `api_key_env` — that field is the *name* of the env var.

---

## Project structure

```
knowledgebase/
├── README.md
├── requirements.txt
├── step1_grobid/          # GROBID client, postprocess, chunking
├── step2_figures/         # PDFFigures2 extract + crop
├── step3_link_figures/    # Link figure paths to chunks
├── step4_embeddings/      # Pluggable embedding (e.g. Zhipu Embedding-3)
├── step5_faiss/           # FAISS index from embeddings
├── step6_sqlite/          # SQLite metadata (faiss_id-aligned)
├── step7_query/           # Retrieval: embed → FAISS → SQLite → paper aggregation
├── step8_llm/             # LLM interface + answer (config-driven)
├── indexes/               # FAISS index + SQLite DB (create as needed)
├── chunk_embedding/       # Chunks with embeddings (Step 4 output)
└── grobid_output/         # GROBID + chunk outputs (example)
```

Step-specific details: see each `stepN_*/README.md` where present.
