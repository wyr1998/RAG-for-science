# Knowledge Base — Install & Use Guide

This guide is for **people who install and use** the Knowledge Base desktop app. It tells you what you need, how to install, and how to index papers and ask questions.

---

## What is Knowledge Base?

Knowledge Base is a **Windows desktop app** that lets you:

1. **Index** a folder of scientific PDF papers (extract text, figures, and build a search index).
2. **Ask questions** in plain language and get answers based on your papers (RAG: retrieval-augmented generation).

---

## What you need before installing

| Requirement | Purpose |
|-------------|--------|
| **Windows 10/11** (64-bit) | The app runs on Windows only. |
| **Docker Desktop** | Runs GROBID (PDF parser). Install it and **start it** when you use the app. Download: [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/). |
| **GROBID** | PDF parsing service; runs as a Docker container. The app starts GROBID automatically when you index—you do not run any Docker commands yourself. Info: [GROBID](https://grobid.github.io/), [GROBID Docker image](https://hub.docker.com/r/grobid/grobid). |
| **Zhipu API keys** | The app uses **Zhipu only**: one key for embeddings (e.g. Embedding-3), one for the LLM. Get your API keys from [Zhipu AI Open Platform](https://open.bigmodel.cn/). |

You do **not** need: Python, Java, Node.js, or Conda. The app ships with everything it needs.

---

## How to install

1. **Install Docker Desktop** (if not already)  
   Download and install from: [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).  
   GROBID runs inside Docker; the app will start the GROBID container when you index—you only need Docker Desktop installed and running.

2. **Get the Knowledge Base installer**  
   You should have a file like `knowledgebase_0.1.0_x64-setup.exe` (or similar name/version).

3. **Run the installer**  
   Double-click the `.exe`, follow the steps (e.g. choose install location, shortcut), and finish.

4. **Start the app**  
   Open **Knowledge Base** from the Start menu or desktop shortcut. The window opens and the app starts its backend automatically. Wait a few seconds for it to be ready.

---

## Before you index: start Docker Desktop

The app needs **GROBID** to parse PDFs. GROBID runs in Docker.

- **Start Docker Desktop** and wait until it is running (whale icon in the system tray).
- You do **not** need to run any `docker run` command. The app starts the GROBID container automatically when you click **Index papers** (as long as Docker Desktop is running).
- Leave Docker Desktop running whenever you use the app to **index** or **add** papers.

---

## How to use the app

### Step 1: Open Settings

Click the **Settings** in the top-right to open the settings panel.

### Step 2: Set your folders and API keys

In Settings, fill in:

| Setting | What to enter |
|--------|----------------|
| **Papers folder path** | The full path to the folder where your PDFs are (e.g. `D:\MyPapers` or `D:\papers\biology`). |
| **Output folder — absolute path** | The full path where the app should save the index and related files (e.g. `D:\KnowledgeBaseOutput\paper`). If you leave this empty, the app uses a default location. Using a path like `D:\...` keeps your index in a fixed place. |
| **Embedding API key** | Your **Zhipu** embedding API key (used for indexing and search). |
| **LLM API key** | Your **Zhipu** LLM API key (used for generating answers). |

- **Automatically obtain images** — Leave checked if you want figures extracted from PDFs; uncheck to index text only (faster).
- Other options (top_k, paper_top_k, llm_chunks_per_paper) can stay at defaults unless you know you need to change them.

Settings are saved automatically.

### Step 3: Index your papers

1. Make sure **Docker Desktop** is running and **Papers folder path** points to a folder that contains your PDFs (the app will start GROBID when you index).
2. In Settings, click **Index papers**.
3. Wait for indexing to finish (it may take a few minutes depending on how many PDFs you have). When it succeeds, the app saves the index paths; you do not need to type them anywhere.

### Step 4: Ask a question

1. Switch to the **AI Assistant** tab (or view).
2. Type your question in the input box and send it.
3. The app searches your indexed papers and uses the LLM to generate an answer. You may see references or evidence from the papers.

**Important:** If you see "Failed to fetch" when asking a question, usually it means the app does not have a valid index yet. Run **Index papers** first and wait until it completes successfully. The app then uses the saved index paths automatically.

---

## Papers tab: browse and manage PDFs

- **Papers** — View your papers by collection, open the list of PDFs.
- You can **add**, **delete**, or **move** PDFs in the papers tree. Use **Add Paper** to add a new PDF and include it in the index without re-indexing everything.

---

## Summary

1. **Install** **Docker Desktop** ([download](https://www.docker.com/products/docker-desktop/)) and the **Knowledge Base** app.
2. When you use the app, **start Docker Desktop** (you do not need to run any GROBID command—the app starts it).
3. In the app **Settings**, set **Papers folder**, **Output folder** (recommended), and your **Zhipu API keys** (embedding + LLM).
4. Click **Index papers** and wait for it to finish.
5. Go to **AI Assistant** and **ask questions**.

No Python or Java installation is required; the app includes everything it needs to index and answer.

---

## Note on scope and future updates

- This app is intended for **research papers** only.

- Chunking is figure-aware (sections and figure references), so it works best on papers that contain **many figures**; papers with little or no figure content may give less useful retrieval.

- Support for **other APIs** is planned.

- Integration with **Semantic Scholar** and **OpenScholar** will be added in a later release.
