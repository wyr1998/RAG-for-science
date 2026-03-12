import React, { useEffect, useMemo, useState } from "react";

const API_TREE = "http://localhost:8000/papers_tree";
const API_CREATE = "http://localhost:8000/subcollections/create";
const API_RENAME = "http://localhost:8000/subcollections/rename";
const API_DELETE = "http://localhost:8000/subcollections/delete";

function buildTreeFromPaths(paths) {
  const pathSet = new Set(paths);
  pathSet.add("");

  const sorted = Array.from(pathSet).sort((a, b) => {
    if (a === "") return -1;
    if (b === "") return 1;
    return a.localeCompare(b);
  });

  const childrenOf = {};
  sorted.forEach((p) => {
    childrenOf[p] = [];
  });

  sorted.forEach((p) => {
    if (p === "") return;
    const idx = p.lastIndexOf("/");
    const parent = idx >= 0 ? p.slice(0, idx) : "";
    if (pathSet.has(parent)) childrenOf[parent].push(p);
  });

  Object.keys(childrenOf).forEach((k) => {
    childrenOf[k].sort((a, b) => a.localeCompare(b));
  });

  return { root: "", childrenOf };
}

function CollectionTree({ tree, expandedPaths, selectedPath, onToggle, onSelect, onNodeContextMenu }) {
  const { root, childrenOf } = tree;

  function renderNode(path, depth) {
    const label = path === "" ? "All" : path.split("/").pop();
    const children = childrenOf[path] || [];
    const isExpanded = expandedPaths.has(path);
    const isSelected = selectedPath === path;
    const hasChildren = children.length > 0;

    return (
      <div key={path || "__root__"} className="collection-tree-node-wrap">
        <div
          className={`collection-tree-node ${isSelected ? "selected" : ""}`}
          style={{ paddingLeft: `${depth * 0.75 + 0.5}rem` }}
          onClick={() => onSelect(path)}
          onContextMenu={(e) => onNodeContextMenu?.(e, path)}
        >
          {hasChildren ? (
            <button
              type="button"
              className="collection-tree-chevron"
              aria-label={isExpanded ? "Collapse" : "Expand"}
              onClick={(e) => {
                e.stopPropagation();
                onToggle(path);
              }}
            >
              {isExpanded ? "▼" : "▶"}
            </button>
          ) : (
            <span className="collection-tree-chevron-placeholder" />
          )}
          <span className="collection-tree-label">{label}</span>
        </div>
        {hasChildren && isExpanded && (
          <div className="collection-tree-children">
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  }

  return <div className="collection-tree">{renderNode(root, 0)}</div>;
}

function PapersCollections({
  papersRoot,
  refreshToken,
  onRefresh,
  onNotify,
  selectedPath,
  onSelectPath,
}) {
  const [subcollections, setSubcollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedPaths, setExpandedPaths] = useState(() => new Set([""]));
  const [menu, setMenu] = useState({ open: false, x: 0, y: 0, path: "" });

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
    const url = `${API_TREE}?papers_root=${encodeURIComponent(root)}`;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText || "Failed to load subcollections");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setSubcollections(data.subcollections || [""]);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load papers");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [papersRoot, refreshToken]);

  const tree = useMemo(() => {
    return buildTreeFromPaths(subcollections);
  }, [subcollections]);

  const handleToggle = (path) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

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

  const showMenu = (e, path) => {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ open: true, x: e.clientX, y: e.clientY, path });
  };

  const apiCall = async (url, body) => {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail = "";
      try {
        const j = await res.json();
        detail = j?.detail || "";
      } catch (_) {
        detail = await res.text();
      }
      throw new Error(detail || `Request failed (${res.status})`);
    }
    return await res.json().catch(() => ({}));
  };

  const doCreate = async () => {
    const base = menu.path ? `${menu.path}/` : "";
    const rel = window.prompt("Create subcollection (relative path):", `${base}NewFolder`);
    if (!rel) return;
    try {
      await apiCall(API_CREATE, { papers_root: papersRoot, subcollection_path: rel });
      onNotify?.(`Created: ${rel}`, "success");
      onRefresh?.();
      setExpandedPaths((prev) => new Set(prev).add(menu.path || ""));
    } catch (e) {
      onNotify?.(e.message || "Create failed", "error");
    }
  };

  const doRename = async () => {
    if (!menu.path) return;
    const rel = window.prompt("Rename subcollection to (relative path):", menu.path);
    if (!rel || rel === menu.path) return;
    try {
      await apiCall(API_RENAME, {
        papers_root: papersRoot,
        subcollection_path: menu.path,
        new_subcollection_path: rel,
      });
      onNotify?.(`Renamed to: ${rel}`, "success");
      if (selectedPath === menu.path) onSelectPath?.(rel);
      onRefresh?.();
    } catch (e) {
      onNotify?.(e.message || "Rename failed", "error");
    }
  };

  const doDelete = async () => {
    if (!menu.path) return;
    const ok = window.confirm(`Delete subcollection folder (must be empty):\n${menu.path}`);
    if (!ok) return;
    try {
      await apiCall(API_DELETE, { papers_root: papersRoot, subcollection_path: menu.path });
      onNotify?.(`Deleted: ${menu.path}`, "success");
      if (selectedPath === menu.path) onSelectPath?.("");
      onRefresh?.();
    } catch (e) {
      onNotify?.(e.message || "Delete failed", "error");
    }
  };

  if (loading) {
    return (
      <div className="sidebar-section">
        <h2 className="sidebar-title">Subcollections</h2>
        <p className="sidebar-hint">Loading…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="sidebar-section">
        <h2 className="sidebar-title">Subcollections</h2>
        <p className="sidebar-hint">{error}</p>
      </div>
    );
  }

  return (
    <div className="sidebar-section sidebar-collections">
      <h2 className="sidebar-title">Subcollections</h2>
      <div onContextMenu={(e) => showMenu(e, "")}>
        <CollectionTree
          tree={tree}
          expandedPaths={expandedPaths}
          selectedPath={selectedPath}
          onToggle={handleToggle}
          onSelect={onSelectPath}
          onNodeContextMenu={showMenu}
        />
      </div>
      {menu.open && (
        <div className="context-menu" style={{ top: menu.y, left: menu.x }}>
          <button type="button" className="context-menu-item" onClick={doCreate}>
            Create…
          </button>
          <button
            type="button"
            className="context-menu-item"
            onClick={doRename}
            disabled={!menu.path}
          >
            Rename…
          </button>
          <button
            type="button"
            className="context-menu-item danger"
            onClick={doDelete}
            disabled={!menu.path}
          >
            Delete…
          </button>
        </div>
      )}
    </div>
  );
}

export default PapersCollections;
