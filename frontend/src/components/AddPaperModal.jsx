import React, { useEffect, useState } from "react";

const ADD_PAPER_URL = "http://localhost:8000/papers/add_and_index";

function AddPaperModal({
  isOpen,
  onClose,
  papersRoot,
  defaultSubcollection,
  faissIndex,
  sqliteDb,
  embedApiKey,
  onAdded,
  onNotify,
}) {
  const [externalPath, setExternalPath] = useState("");
  const [subcollection, setSubcollection] = useState(defaultSubcollection || "");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setExternalPath("");
    setSubcollection(defaultSubcollection || "");
  }, [isOpen, defaultSubcollection]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!papersRoot?.trim()) {
      onNotify?.("Set papers folder path in Settings first", "error");
      return;
    }
    if (!faissIndex || !sqliteDb) {
      onNotify?.("Run Index papers once before adding individual papers", "error");
      return;
    }
    if (!externalPath.trim()) {
      onNotify?.("Enter a full path to a PDF file", "error");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(ADD_PAPER_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          papers_root: papersRoot.trim(),
          external_path: externalPath.trim(),
          target_subcollection_path: subcollection.trim(),
          faiss_index: faissIndex,
          sqlite_db: sqliteDb,
          ...(embedApiKey?.trim() && { embed_api_key: embedApiKey.trim() }),
        }),
      });
      if (!res.ok) {
        let detail = "";
        try {
          const j = await res.json();
          detail = j?.detail || "";
        } catch (_) {
          detail = await res.text();
        }
        throw new Error(detail || `Add paper failed (${res.status})`);
      }
      await res.json().catch(() => ({}));
      onNotify?.("Added and indexed paper", "success");
      onAdded?.();
      onClose();
    } catch (err) {
      onNotify?.(err.message || "Add paper failed", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="settings-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-paper-modal-title"
      onClick={(e) => e.target === e.currentTarget && !submitting && onClose()}
    >
      <div className="settings-modal">
        <div className="settings-modal-header">
          <h2 id="add-paper-modal-title" className="settings-modal-title">
            Add Paper
          </h2>
          <button
            type="button"
            className="settings-modal-close"
            onClick={onClose}
            aria-label="Close add paper dialog"
            disabled={submitting}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="settings-modal-body">
          <form onSubmit={handleSubmit} className="settings-panel">
            <div className="settings-fields">
              <div>
                <span className="settings-label">Papers root</span>
                <div className="settings-input readonly">
                  {papersRoot || <span style={{ color: "#6b7280" }}>Not set</span>}
                </div>
              </div>
              <label>
                <span className="settings-label">External PDF path</span>
                <input
                  type="text"
                  className="settings-input"
                  value={externalPath}
                  onChange={(e) => setExternalPath(e.target.value)}
                  placeholder="e.g. C:/Users/Me/Downloads/article.pdf"
                />
              </label>
              <label>
                <span className="settings-label">Target subcollection (relative to papers root)</span>
                <input
                  type="text"
                  className="settings-input"
                  value={subcollection}
                  onChange={(e) => setSubcollection(e.target.value)}
                  placeholder='e.g. ML/2024 (leave blank for root)'
                />
              </label>
            </div>
            <div className="settings-index-actions">
              <button
                type="submit"
                className="settings-index-btn"
                disabled={submitting}
              >
                {submitting ? "Adding…" : "Add and index"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default AddPaperModal;

