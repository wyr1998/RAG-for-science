import React from "react";
import PapersCollections from "./PapersCollections.jsx";

const MAX_HISTORY = 10;
const HISTORY_PREVIEW_LEN = 50;

function preview(text) {
  if (!text || typeof text !== "string") return "";
  const t = text.trim();
  return t.length <= HISTORY_PREVIEW_LEN
    ? t
    : t.slice(0, HISTORY_PREVIEW_LEN) + "…";
}

function Sidebar({
  activeView,
  onViewChange,
  history,
  selectedHistoryId,
  onSelectHistory,
  papersRoot,
  papersRefreshToken,
  onPapersRefresh,
  onNotify,
  selectedSubcollectionPath,
  onSelectSubcollectionPath,
}) {
  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <button
          type="button"
          className={`sidebar-nav-item ${activeView === "papers" ? "active" : ""}`}
          onClick={() => onViewChange("papers")}
        >
          Papers
        </button>
        <button
          type="button"
          className={`sidebar-nav-item ${activeView === "assistant" ? "active" : ""}`}
          onClick={() => onViewChange("assistant")}
        >
          AI Assistant
        </button>
      </nav>

      {activeView === "papers" ? (
        <PapersCollections
          papersRoot={papersRoot}
          refreshToken={papersRefreshToken}
          onRefresh={onPapersRefresh}
          onNotify={onNotify}
          selectedPath={selectedSubcollectionPath}
          onSelectPath={onSelectSubcollectionPath}
        />
      ) : (
        <div className="sidebar-history">
          <h2 className="sidebar-title">History</h2>
          <p className="sidebar-hint">Last {MAX_HISTORY} questions</p>
          <ul className="history-list">
            {history.length === 0 && (
              <li className="history-empty">No questions yet.</li>
            )}
            {history.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  className={`history-item ${selectedHistoryId === entry.id ? "active" : ""}`}
                  onClick={() => onSelectHistory(entry.id)}
                >
                  {preview(entry.question)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

export default Sidebar;
