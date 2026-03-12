import React from "react";
import EvidencePanel from "./EvidencePanel.jsx";

function MessageBubble({ message, isEvidenceExpanded, onToggleEvidence }) {
  const { id, role, content, retrieval } = message;
  const hasEvidence = role === "assistant" && retrieval?.papers?.length > 0;

  return (
    <div
      className={`message message-${role}`}
      data-role={role}
    >
      <div className="message-bubble">
        <div className="message-content">{content}</div>
        {hasEvidence && (
          <>
            <button
              type="button"
              className="btn-evidence"
              onClick={() => onToggleEvidence(id)}
              aria-expanded={isEvidenceExpanded}
            >
              {isEvidenceExpanded ? "Hide Evidence" : "Show Evidence"}
            </button>
            {isEvidenceExpanded && <EvidencePanel retrieval={retrieval} />}
          </>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;
