import React, { useState, useRef, useEffect } from "react";
import Sidebar from "./components/Sidebar.jsx";
import ChatMessages from "./components/ChatMessages.jsx";
import SettingsModal from "./components/SettingsModal.jsx";
import PapersView from "./components/PapersView.jsx";
import AddPaperModal from "./components/AddPaperModal.jsx";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const API_URL = `${API_BASE_URL}/ask`;
const INDEX_URL = `${API_BASE_URL}/index`;
const MAX_HISTORY = 10;

function optionalInt(v) {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isInteger(n) && n >= 1 ? n : null;
}
const STORAGE_KEYS = {
  model: "kb_model",
  fontSize: "kb_fontSize",
  systemPrompt: "kb_systemPrompt",
  papersFolderPath: "kb_papersFolderPath",
  outputFolderPath: "kb_outputFolderPath",
  embedApiKey: "kb_embedApiKey",
  llmApiKey: "kb_llmApiKey",
  autoObtainImages: "kb_autoObtainImages",
  topK: "kb_topK",
  paperTopK: "kb_paperTopK",
  llmChunksPerPaper: "kb_llmChunksPerPaper",
  faissIndex: "kb_faissIndex",
  sqliteDb: "kb_sqliteDb",
  figuresRoot: "kb_figuresRoot",
};

function App() {
  const [history, setHistory] = useState([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [expandedEvidenceIds, setExpandedEvidenceIds] = useState(new Set());
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [fontSize, setFontSize] = useState(null);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [papersFolderPath, setPapersFolderPath] = useState("");
  const [outputFolderPath, setOutputFolderPath] = useState("");
  const [embedApiKey, setEmbedApiKey] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [autoObtainImages, setAutoObtainImages] = useState(true);
  const [topK, setTopK] = useState("");
  const [paperTopK, setPaperTopK] = useState("");
  const [llmChunksPerPaper, setLlmChunksPerPaper] = useState("");
  const [faissIndex, setFaissIndex] = useState("");
  const [sqliteDb, setSqliteDb] = useState("");
  const [figuresRoot, setFiguresRoot] = useState("");
  const [indexLoading, setIndexLoading] = useState(false);
  const [indexError, setIndexError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeView, setActiveView] = useState("assistant");
  const [selectedSubcollectionPath, setSelectedSubcollectionPath] = useState("");
  const [papersRefreshToken, setPapersRefreshToken] = useState(0);
  const [papersNotice, setPapersNotice] = useState(null);
  const [addPaperOpen, setAddPaperOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    try {
      const storedModel = localStorage.getItem(STORAGE_KEYS.model);
      const storedFontSize = localStorage.getItem(STORAGE_KEYS.fontSize);
      const storedSystemPrompt = localStorage.getItem(STORAGE_KEYS.systemPrompt);
      const storedPapersFolderPath = localStorage.getItem(STORAGE_KEYS.papersFolderPath);
      const storedOutputFolderPath = localStorage.getItem(STORAGE_KEYS.outputFolderPath);
      const storedEmbedApiKey = localStorage.getItem(STORAGE_KEYS.embedApiKey);
      const storedLlmApiKey = localStorage.getItem(STORAGE_KEYS.llmApiKey);
      const storedAutoObtainImages = localStorage.getItem(STORAGE_KEYS.autoObtainImages);
      const storedTopK = localStorage.getItem(STORAGE_KEYS.topK);
      const storedPaperTopK = localStorage.getItem(STORAGE_KEYS.paperTopK);
      const storedLlmChunksPerPaper = localStorage.getItem(STORAGE_KEYS.llmChunksPerPaper);
      const storedFaissIndex = localStorage.getItem(STORAGE_KEYS.faissIndex);
      const storedSqliteDb = localStorage.getItem(STORAGE_KEYS.sqliteDb);
      const storedFiguresRoot = localStorage.getItem(STORAGE_KEYS.figuresRoot);
      if (storedModel != null) setModel(storedModel);
      if (storedFontSize != null) setFontSize(Number(storedFontSize) || null);
      if (storedSystemPrompt != null) setSystemPrompt(storedSystemPrompt);
      if (storedPapersFolderPath != null) setPapersFolderPath(storedPapersFolderPath);
      if (storedOutputFolderPath != null) setOutputFolderPath(storedOutputFolderPath);
      if (storedEmbedApiKey != null) setEmbedApiKey(storedEmbedApiKey);
      if (storedLlmApiKey != null) setLlmApiKey(storedLlmApiKey);
      if (storedAutoObtainImages != null) setAutoObtainImages(storedAutoObtainImages !== "0");
      if (storedTopK != null) setTopK(storedTopK);
      if (storedPaperTopK != null) setPaperTopK(storedPaperTopK);
      if (storedLlmChunksPerPaper != null) setLlmChunksPerPaper(storedLlmChunksPerPaper);
      if (storedFaissIndex != null) setFaissIndex(storedFaissIndex);
      if (storedSqliteDb != null) setSqliteDb(storedSqliteDb);
      if (storedFiguresRoot != null) setFiguresRoot(storedFiguresRoot);
    } catch (_) {}
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, selectedHistoryId, history, loading]);

  const toggleEvidence = (messageId) => {
    setExpandedEvidenceIds((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) next.delete(messageId);
      else next.add(messageId);
      return next;
    });
  };

  const displayMessages =
    selectedHistoryId !== null
      ? (() => {
          const entry = history.find((h) => h.id === selectedHistoryId);
          if (!entry) return [];
          return [
            { id: `${entry.id}-user`, role: "user", content: entry.question },
            {
              id: `${entry.id}-assistant`,
              role: "assistant",
              content: entry.answer,
              retrieval: entry.retrieval ?? null,
            },
          ];
        })()
      : messages;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    const userContent = question.trim();
    setQuestion("");
    setLoading(true);
    setError("");
    setSelectedHistoryId(null);

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: userContent,
    };

    const askBody = {
      query: userContent,
      ...(embedApiKey?.trim() && { embed_api_key: embedApiKey.trim() }),
      ...(llmApiKey?.trim() && { llm_api_key: llmApiKey.trim() }),
      ...(faissIndex?.trim() && { faiss_index: faissIndex.trim() }),
      ...(sqliteDb?.trim() && { sqlite_db: sqliteDb.trim() }),
      ...(figuresRoot?.trim() && { figures_root: figuresRoot.trim() }),
      ...(optionalInt(topK) != null && { top_k: optionalInt(topK) }),
      ...(optionalInt(paperTopK) != null && { paper_top_k: optionalInt(paperTopK) }),
      ...(optionalInt(llmChunksPerPaper) != null && { llm_chunks_per_paper: optionalInt(llmChunksPerPaper) }),
    };
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(askBody),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed with status ${res.status}`);
      }

      const data = await res.json();
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer || "",
        retrieval: data.retrieval || null,
      };

      setMessages([userMessage, assistantMessage]);

      const entry = {
        id: `hist-${Date.now()}`,
        question: userContent,
        answer: data.answer || "",
        retrieval: data.retrieval || null,
      };
      setHistory((prev) => [entry, ...prev].slice(0, MAX_HISTORY));
    } catch (err) {
      console.error(err);
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleIndex = async () => {
    if (!papersFolderPath?.trim()) {
      setIndexError("Set papers folder path first.");
      return;
    }
    setIndexLoading(true);
    setIndexError("");
    try {
      const res = await fetch(INDEX_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          papers_folder: papersFolderPath.trim(),
          auto_figures: autoObtainImages,
          ...(outputFolderPath?.trim() && { output_base: outputFolderPath.trim() }),
          ...(embedApiKey?.trim() && { embed_api_key: embedApiKey.trim() }),
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Index failed: ${res.status}`);
      }
      const data = await res.json();
      if (data.faiss_index) {
        setFaissIndex(data.faiss_index);
        try {
          localStorage.setItem(STORAGE_KEYS.faissIndex, data.faiss_index);
        } catch (_) {}
      }
      if (data.sqlite_db) {
        setSqliteDb(data.sqlite_db);
        try {
          localStorage.setItem(STORAGE_KEYS.sqliteDb, data.sqlite_db);
        } catch (_) {}
      }
      if (data.figures_root != null) {
        setFiguresRoot(data.figures_root);
        try {
          localStorage.setItem(STORAGE_KEYS.figuresRoot, data.figures_root);
        } catch (_) {}
      }
    } catch (err) {
      console.error(err);
      setIndexError(err.message || "Index failed.");
    } finally {
      setIndexLoading(false);
    }
  };

  const refreshPapers = () => setPapersRefreshToken((x) => x + 1);

  const notify = (message, kind = "info") => {
    setPapersNotice({ message, kind, ts: Date.now() });
    // Auto-hide
    window.setTimeout(() => {
      setPapersNotice((prev) => (prev && prev.message === message ? null : prev));
    }, 4000);
  };

  return (
    <div className="app">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        history={history}
        selectedHistoryId={selectedHistoryId}
        onSelectHistory={setSelectedHistoryId}
        papersRoot={papersFolderPath}
        papersRefreshToken={papersRefreshToken}
        onPapersRefresh={refreshPapers}
        onNotify={notify}
        selectedSubcollectionPath={selectedSubcollectionPath}
        onSelectSubcollectionPath={setSelectedSubcollectionPath}
      />

      <div className="chat-column">
        <header className="header">
          <div className="header-left">
            <h1>Paper Knowledge Base</h1>
            <p>Ask questions over your indexed scientific papers.</p>
          </div>
          <button
            type="button"
            className="header-settings-btn"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            aria-label="Open settings"
          >
            <svg className="settings-gear" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        </header>

        {settingsOpen && (
          <SettingsModal
            model={model}
            fontSize={fontSize}
            systemPrompt={systemPrompt}
            papersFolderPath={papersFolderPath}
        outputFolderPath={outputFolderPath}
            embedApiKey={embedApiKey}
            llmApiKey={llmApiKey}
            autoObtainImages={autoObtainImages}
            topK={topK}
            paperTopK={paperTopK}
            llmChunksPerPaper={llmChunksPerPaper}
            onModelChange={setModel}
            onFontSizeChange={setFontSize}
            onSystemPromptChange={setSystemPrompt}
            onPapersFolderPathChange={setPapersFolderPath}
        onOutputFolderPathChange={setOutputFolderPath}
            onEmbedApiKeyChange={setEmbedApiKey}
            onLlmApiKeyChange={setLlmApiKey}
            onAutoObtainImagesChange={setAutoObtainImages}
            onTopKChange={setTopK}
            onPaperTopKChange={setPaperTopK}
            onLlmChunksPerPaperChange={setLlmChunksPerPaper}
            onClose={() => setSettingsOpen(false)}
            onIndex={handleIndex}
            indexLoading={indexLoading}
            indexError={indexError}
          />
        )}

        {activeView === "papers" ? (
          <main className="chat-main content-area">
            <div className="papers-toolbar">
              <button
                type="button"
                className="papers-add-btn"
                onClick={() => setAddPaperOpen(true)}
                disabled={!papersFolderPath?.trim() || !faissIndex || !sqliteDb}
                title={
                  !papersFolderPath?.trim()
                    ? "Set papers folder path in Settings first"
                    : !faissIndex || !sqliteDb
                    ? "Run Index papers once before adding individually"
                    : "Add a new paper from an external path"
                }
              >
                Add Paper
              </button>
            </div>
            {papersNotice && (
              <div className={`papers-notice ${papersNotice.kind}`}>
                {papersNotice.message}
              </div>
            )}
            <PapersView
              papersRoot={papersFolderPath}
              selectedPath={selectedSubcollectionPath}
              refreshToken={papersRefreshToken}
              onRefresh={refreshPapers}
              onNotify={notify}
            />
            {addPaperOpen && (
              <AddPaperModal
                isOpen={addPaperOpen}
                onClose={() => setAddPaperOpen(false)}
                papersRoot={papersFolderPath}
                defaultSubcollection={selectedSubcollectionPath}
                faissIndex={faissIndex}
                sqliteDb={sqliteDb}
                embedApiKey={embedApiKey}
                onAdded={refreshPapers}
                onNotify={notify}
              />
            )}
          </main>
        ) : (
          <main className="chat-main">
            <ChatMessages
              messages={displayMessages}
              expandedEvidenceIds={expandedEvidenceIds}
              onToggleEvidence={toggleEvidence}
              loading={loading}
              messagesEndRef={messagesEndRef}
              fontSize={fontSize}
            />

            {error && <div className="error">{error}</div>}

            <section className="input-section">
              <form onSubmit={handleSubmit}>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder="Ask a question about your papers..."
                  rows={2}
                  disabled={loading}
                />
                <button type="submit" disabled={loading || !question.trim()}>
                  {loading ? "Asking..." : "Send"}
                </button>
              </form>
            </section>
          </main>
        )}
      </div>
    </div>
  );
}

export default App;
