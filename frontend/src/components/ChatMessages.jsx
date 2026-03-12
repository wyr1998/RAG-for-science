import React from "react";
import MessageBubble from "./MessageBubble.jsx";

function ChatMessages({
  messages,
  expandedEvidenceIds,
  onToggleEvidence,
  loading,
  messagesEndRef,
  fontSize,
}) {
  return (
    <div
      className="messages-container"
      style={fontSize != null ? { fontSize: `${fontSize}px` } : undefined}
    >
      {messages.length === 0 && !loading && (
        <div className="empty-state">
          Ask a question about your papers, or choose one from the left.
        </div>
      )}

      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          isEvidenceExpanded={expandedEvidenceIds.has(msg.id)}
          onToggleEvidence={onToggleEvidence}
        />
      ))}

      {loading && (
        <div className="message message-assistant">
          <div className="message-bubble">
            <div className="message-content typing">Thinking...</div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}

export default ChatMessages;
