import React, { useState, useEffect } from "react";

const API_PAPERS = "http://localhost:8000/papers_fs";
const API_MOVE = "http://localhost:8000/papers/move";
const API_DELETE = "http://localhost:8000/papers/delete";

function PapersView({
  papersRoot,
  selectedPath = "",
  refreshToken,
  onRefresh,
  onNotify,
}) {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState({ open: false, x: 0, y: 0, paper: null });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    const root = papersRoot?.trim();
    if (!root) {
      setLoading(false);
      setError("Set papers folder path in Settings first.");
      return () => {
        cancelled = true;
      };
    }
    const url = `${API_PAPERS}?papers_root=${encodeURIComponent(root)}&subcollection_path=${encodeURIComponent(selectedPath || "")}`;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText || "Failed to load papers");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setPapers(data.papers || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load papers");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [papersRoot, selectedPath, refreshToken]);

  useEffect(() => {
    if (!menu.open) return undefined;
    const close = () => setMenu((m) => ({ ...m, open: false }));
    window.addEventListener("click", close);
    window.addEventListener("blur", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("blur", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [menu.open]);

  if (loading) {
    return (
      <div className="papers-view">
        <p className="papers-loading">Loading papers…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="papers-view">
        <p className="papers-error">{error}</p>
      </div>
    );
  }

  if (papers.length === 0) {
    return (
      <div className="papers-view">
        <p className="papers-empty">
          {selectedPath ? "No papers in this subcollection." : "No papers in the knowledge base yet."}
        </p>
      </div>
    );
  }

  const showMenu = (e, paper) => {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ open: true, x: e.clientX, y: e.clientY, paper });
  };

  const movePaper = async () => {
    const p = menu.paper;
    if (!p?.rel_path) return;
    const target = window.prompt("Move to subcollection (relative path, empty for root):", "");
    if (target == null) return;
    try {
      const res = await fetch(API_MOVE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          papers_root: papersRoot,
          source_rel_path: p.rel_path,
          target_subcollection_path: target,
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
        throw new Error(detail || `Move failed (${res.status})`);
      }
      onNotify?.(`Moved: ${p.file_name}`, "success");
      onRefresh?.();
    } catch (e) {
      onNotify?.(e.message || "Move failed", "error");
    }
  };

  const deletePaper = async () => {
    const p = menu.paper;
    if (!p?.rel_path) return;
    const ok = window.confirm(`Delete this paper from disk?\n\n${p.rel_path}`);
    if (!ok) return;
    try {
      const res = await fetch(API_DELETE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          papers_root: papersRoot,
          rel_path: p.rel_path,
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
        throw new Error(detail || `Delete failed (${res.status})`);
      }
      onNotify?.(`Deleted: ${p.file_name}`, "success");
      setMenu((m) => ({ ...m, open: false }));
      onRefresh?.();
    } catch (e) {
      onNotify?.(e.message || "Delete failed", "error");
    }
  };

  return (
    <div className="papers-view papers-list-only">
      <ul className="papers-list">
        {papers.map((paper, idx) => (
          <li
            key={paper.rel_path || paper.file_name || idx}
            className="paper-list-item"
            onContextMenu={(e) => showMenu(e, paper)}
            title={paper.rel_path || paper.file_name || ""}
          >
            <span className="paper-list-title">{paper.title}</span>
            {paper.file_name && (
              <span className="paper-list-filename">{paper.file_name}</span>
            )}
          </li>
        ))}
      </ul>
      {menu.open && (
        <div className="context-menu" style={{ top: menu.y, left: menu.x }}>
          <button type="button" className="context-menu-item" onClick={movePaper}>
            Move to…
          </button>
          <button type="button" className="context-menu-item danger" onClick={deletePaper}>
            Delete…
          </button>
        </div>
      )}
    </div>
  );
}

export default PapersView;
