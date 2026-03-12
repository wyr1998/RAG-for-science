import React, { useState } from "react";

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
};

function SettingsPanel({
  model,
  fontSize,
  systemPrompt,
  papersFolderPath,
  outputFolderPath,
  embedApiKey,
  llmApiKey,
  autoObtainImages,
  topK,
  paperTopK,
  llmChunksPerPaper,
  onModelChange,
  onFontSizeChange,
  onSystemPromptChange,
  onPapersFolderPathChange,
  onOutputFolderPathChange,
  onEmbedApiKeyChange,
  onLlmApiKeyChange,
  onAutoObtainImagesChange,
  onTopKChange,
  onPaperTopKChange,
  onLlmChunksPerPaperChange,
  hideTitle = false,
}) {
  const [paramInfoOpen, setParamInfoOpen] = useState(null);

  const PARAM_INSTRUCTIONS = {
    top_k: "Number of chunks to retrieve from the index. Default: 50.",
    paper_top_k: "Number of top papers to aggregate for context. Default: 5.",
    llm_chunks_per_paper: "Max chunks per paper sent to the LLM. Default: 3.",
  };

  const persistModel = (value) => {
    onModelChange(value);
    try {
      localStorage.setItem(STORAGE_KEYS.model, value);
    } catch (_) {}
  };

  const persistFontSize = (value) => {
    const num = value === "" ? undefined : Number(value);
    onFontSizeChange(num);
    try {
      if (num != null) localStorage.setItem(STORAGE_KEYS.fontSize, String(num));
      else localStorage.removeItem(STORAGE_KEYS.fontSize);
    } catch (_) {}
  };

  const persistSystemPrompt = (value) => {
    onSystemPromptChange(value);
    try {
      localStorage.setItem(STORAGE_KEYS.systemPrompt, value);
    } catch (_) {}
  };

  const persistPapersFolderPath = (value) => {
    onPapersFolderPathChange(value);
    try {
      localStorage.setItem(STORAGE_KEYS.papersFolderPath, value);
    } catch (_) {}
  };

  const persistOutputFolderPath = (value) => {
    onOutputFolderPathChange(value);
    try {
      if (value) localStorage.setItem(STORAGE_KEYS.outputFolderPath, value);
      else localStorage.removeItem(STORAGE_KEYS.outputFolderPath);
    } catch (_) {}
  };

  const persistEmbedApiKey = (value) => {
    onEmbedApiKeyChange(value);
    try {
      localStorage.setItem(STORAGE_KEYS.embedApiKey, value);
    } catch (_) {}
  };

  const persistLlmApiKey = (value) => {
    onLlmApiKeyChange(value);
    try {
      localStorage.setItem(STORAGE_KEYS.llmApiKey, value);
    } catch (_) {}
  };

  const persistAutoObtainImages = (checked) => {
    onAutoObtainImagesChange(checked);
    try {
      localStorage.setItem(STORAGE_KEYS.autoObtainImages, checked ? "1" : "0");
    } catch (_) {}
  };

  const persistTopK = (value) => {
    onTopKChange(value);
    try {
      if (value !== "") localStorage.setItem(STORAGE_KEYS.topK, value);
      else localStorage.removeItem(STORAGE_KEYS.topK);
    } catch (_) {}
  };

  const persistPaperTopK = (value) => {
    onPaperTopKChange(value);
    try {
      if (value !== "") localStorage.setItem(STORAGE_KEYS.paperTopK, value);
      else localStorage.removeItem(STORAGE_KEYS.paperTopK);
    } catch (_) {}
  };

  const persistLlmChunksPerPaper = (value) => {
    onLlmChunksPerPaperChange(value);
    try {
      if (value !== "") localStorage.setItem(STORAGE_KEYS.llmChunksPerPaper, value);
      else localStorage.removeItem(STORAGE_KEYS.llmChunksPerPaper);
    } catch (_) {}
  };

  return (
    <div className="settings-panel">
      {!hideTitle && <h2 className="sidebar-title">Settings</h2>}
      <div className="settings-fields">
        <label className="settings-checkbox-label">
          <input
            type="checkbox"
            checked={autoObtainImages !== false}
            onChange={(e) => persistAutoObtainImages(e.target.checked)}
            className="settings-checkbox"
          />
          <span className="settings-label">Automatically obtain images</span>
        </label>
        <label>
          <span className="settings-label">Papers folder path</span>
          <input
            type="text"
            value={papersFolderPath ?? ""}
            onChange={(e) => persistPapersFolderPath(e.target.value)}
            placeholder="e.g. D:/papers or path/to/papers"
            className="settings-input"
          />
        </label>
        <label>
          <span className="settings-label">Output folder — absolute path (optional)</span>
          <input
            type="text"
            value={outputFolderPath ?? ""}
            onChange={(e) => persistOutputFolderPath(e.target.value)}
            placeholder="e.g. D:/environment/knowledgebase/backend_output/paper"
            className="settings-input"
          />
        </label>
        <label>
          <span className="settings-label">Embedding API key</span>
          <input
            type="password"
            value={embedApiKey ?? ""}
            onChange={(e) => persistEmbedApiKey(e.target.value)}
            placeholder="Optional; set in app or env"
            className="settings-input"
          />
        </label>
        <label>
          <span className="settings-label">LLM API key</span>
          <input
            type="password"
            value={llmApiKey ?? ""}
            onChange={(e) => persistLlmApiKey(e.target.value)}
            placeholder="Optional; set in app or env"
            className="settings-input"
          />
        </label>
        <label>
          <span className="settings-label">Model</span>
          <input
            type="text"
            value={model ?? ""}
            onChange={(e) => persistModel(e.target.value)}
            placeholder="e.g. glm-4"
            className="settings-input"
          />
        </label>
        <label>
          <span className="settings-label">Font size</span>
          <input
            type="number"
            min={10}
            max={24}
            value={fontSize ?? ""}
            onChange={(e) => persistFontSize(e.target.value)}
            placeholder="14"
            className="settings-input"
          />
        </label>
        <label className="settings-param-row">
          <span className="settings-label-inline">
            top_k (optional)
            <button
              type="button"
              className="settings-param-info-icon"
              onClick={() => setParamInfoOpen((v) => (v === "top_k" ? null : "top_k"))}
              title="Info"
              aria-label="Show top_k instruction"
            >
              i
            </button>
          </span>
          {paramInfoOpen === "top_k" && (
            <div className="settings-param-instruction">{PARAM_INSTRUCTIONS.top_k}</div>
          )}
          <input
            type="number"
            min={1}
            value={topK ?? ""}
            onChange={(e) => persistTopK(e.target.value)}
            placeholder="50"
            className="settings-input"
          />
        </label>
        <label className="settings-param-row">
          <span className="settings-label-inline">
            paper_top_k (optional)
            <button
              type="button"
              className="settings-param-info-icon"
              onClick={() => setParamInfoOpen((v) => (v === "paper_top_k" ? null : "paper_top_k"))}
              title="Info"
              aria-label="Show paper_top_k instruction"
            >
              i
            </button>
          </span>
          {paramInfoOpen === "paper_top_k" && (
            <div className="settings-param-instruction">{PARAM_INSTRUCTIONS.paper_top_k}</div>
          )}
          <input
            type="number"
            min={1}
            value={paperTopK ?? ""}
            onChange={(e) => persistPaperTopK(e.target.value)}
            placeholder="5"
            className="settings-input"
          />
        </label>
        <label className="settings-param-row">
          <span className="settings-label-inline">
            llm_chunks_per_paper (optional)
            <button
              type="button"
              className="settings-param-info-icon"
              onClick={() => setParamInfoOpen((v) => (v === "llm_chunks_per_paper" ? null : "llm_chunks_per_paper"))}
              title="Info"
              aria-label="Show llm_chunks_per_paper instruction"
            >
              i
            </button>
          </span>
          {paramInfoOpen === "llm_chunks_per_paper" && (
            <div className="settings-param-instruction">{PARAM_INSTRUCTIONS.llm_chunks_per_paper}</div>
          )}
          <input
            type="number"
            min={1}
            value={llmChunksPerPaper ?? ""}
            onChange={(e) => persistLlmChunksPerPaper(e.target.value)}
            placeholder="3"
            className="settings-input"
          />
        </label>
        <label>
          <span className="settings-label">System prompt</span>
          <textarea
            value={systemPrompt ?? ""}
            onChange={(e) => persistSystemPrompt(e.target.value)}
            placeholder="Optional system prompt"
            rows={2}
            className="settings-textarea"
          />
        </label>
      </div>
    </div>
  );
}

export default SettingsPanel;
