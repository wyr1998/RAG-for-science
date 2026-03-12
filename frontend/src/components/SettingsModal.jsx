import React, { useEffect } from "react";
import SettingsPanel from "./SettingsPanel.jsx";

function SettingsModal({
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
  onClose,
  onIndex,
  indexLoading = false,
  indexError = "",
}) {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  return (
    <div
      className="settings-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="settings-modal">
        <div className="settings-modal-header">
          <h2 id="settings-modal-title" className="settings-modal-title">
            Settings
          </h2>
          <button
            type="button"
            className="settings-modal-close"
            onClick={onClose}
            aria-label="Close settings"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="settings-modal-body">
          <SettingsPanel
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
            onModelChange={onModelChange}
            onFontSizeChange={onFontSizeChange}
            onSystemPromptChange={onSystemPromptChange}
            onPapersFolderPathChange={onPapersFolderPathChange}
            onOutputFolderPathChange={onOutputFolderPathChange}
            onEmbedApiKeyChange={onEmbedApiKeyChange}
            onLlmApiKeyChange={onLlmApiKeyChange}
            onAutoObtainImagesChange={onAutoObtainImagesChange}
            onTopKChange={onTopKChange}
            onPaperTopKChange={onPaperTopKChange}
            onLlmChunksPerPaperChange={onLlmChunksPerPaperChange}
            hideTitle
          />
          {onIndex && (
            <div className="settings-index-actions">
              <button
                type="button"
                className="settings-index-btn"
                onClick={onIndex}
                disabled={indexLoading || !papersFolderPath?.trim()}
              >
                {indexLoading ? "Indexing…" : "Index papers"}
              </button>
              {indexError && <p className="settings-index-error">{indexError}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
