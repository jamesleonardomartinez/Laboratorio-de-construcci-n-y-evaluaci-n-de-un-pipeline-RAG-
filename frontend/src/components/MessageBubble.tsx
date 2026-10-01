import type { ChatMessage, MemoryInfo } from "../types";
import { SourceChip } from "./SourceChip";

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M6 2h8l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
      <path d="M14 2v5h5" strokeLinejoin="round" />
      <path d="M8 13h8M8 17h8" strokeLinecap="round" />
    </svg>
  );
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.kind === "attachment") {
    return (
      <div className="message-row user">
        <div className="bubble attachment-card">
          <span className="attachment-icon">
            <FileIcon />
          </span>
          <div className="attachment-info">
            <div className="attachment-name">{message.fileName}</div>
            <AttachmentStatusLine message={message} />
          </div>
        </div>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="message-row user">
        <div className="bubble">{message.text}</div>
      </div>
    );
  }

  const isEmptyStreaming = !message.text && message.streaming;

  return (
    <div className="message-row assistant">
      <span className="avatar-mark" aria-hidden="true">
        IA
      </span>
      <div className="bubble">
        {isEmptyStreaming ? (
          <span className="typing-dots" aria-label="Generando respuesta">
            <span />
            <span />
            <span />
          </span>
        ) : (
          <>
            {message.text}
            {message.streaming && <span className="stream-caret" aria-hidden="true" />}
          </>
        )}
        {message.sources.length > 0 && (
          <div className="source-chip-row">
            {message.sources.map((s, i) => (
              <SourceChip key={`${s.source_id}-${s.section}-${i}`} source={s} />
            ))}
          </div>
        )}
        {message.memory && <MemoryNote memory={message.memory} />}
      </div>
    </div>
  );
}

function MemoryNote({ memory }: { memory: MemoryInfo }) {
  const tooltip = memory.items.length > 0 ? memory.items.join("\n\n") : undefined;
  return (
    <div className="memory-note" title={tooltip}>
      <span className="memory-note-icon" aria-hidden="true">
        🧠
      </span>
      {memory.count > 0
        ? `${memory.count} recuerdo${memory.count === 1 ? "" : "s"} usado${memory.count === 1 ? "" : "s"}`
        : "Sin recuerdos previos relevantes"}
    </div>
  );
}

function AttachmentStatusLine({
  message,
}: {
  message: Extract<ChatMessage, { kind: "attachment" }>;
}) {
  if (message.status === "processing") {
    return (
      <div className="attachment-status processing">
        <span className="status-dot" />
        Procesando {message.fileName}…
      </div>
    );
  }
  if (message.status === "ready") {
    return (
      <div className="attachment-status ready">
        <span className="status-dot" />
        Listo · {message.chunkCount ?? 0} fragmentos indexados
      </div>
    );
  }
  return (
    <div className="attachment-status failed">
      <span className="status-dot" />
      Error: {message.error}
    </div>
  );
}
