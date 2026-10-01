import { useCallback, useEffect, useState } from "react";
import { deleteSource, listSources } from "../api";
import { useChatStream } from "../hooks/useChatStream";
import { useUpload } from "../hooks/useUpload";
import type {
  AssistantMessage,
  AttachmentStatus,
  ChatMessage,
  IndexedSource,
  MemoryInfo,
  SourceCitation,
  TokenUsage,
} from "../types";
import { MessageBubble } from "./MessageBubble";
import { UploadDropzone } from "./UploadDropzone";

function newId(): string {
  return crypto.randomUUID();
}

const CONVERSATION_STORAGE_PREFIX = "rag-lab.conversation.";

function loadConversationId(projectId: string): string {
  const key = `${CONVERSATION_STORAGE_PREFIX}${projectId}`;
  try {
    const existing = localStorage.getItem(key);
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem(key, created);
    return created;
  } catch {
    return crypto.randomUUID();
  }
}

function EmptyStateIcon() {
  return (
    <svg viewBox="0 0 48 48" width="40" height="40" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M24 10c-4-3-10-4-15-2v26c5-2 11-1 15 2 4-3 10-4 15-2V8c-5-2-11-1-15 2z" strokeLinejoin="round" />
      <path d="M24 10v26" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 12h16M13 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const EMPTY_USAGE: TokenUsage = {
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
};

function formatTokens(value: number): string {
  return value.toLocaleString("es-ES");
}

function TokenCounter({
  session,
  last,
  requests,
}: {
  session: TokenUsage;
  last: TokenUsage | null;
  requests: number;
}) {
  return (
    <aside className="chat-panel chat-panel-right" aria-label="Contador de tokens">
      <div className="panel-header">
        <span className="panel-kicker">Consumo</span>
        <h2 className="panel-title">Tokens</h2>
      </div>

      <div className="token-total">
        <span className="token-total-value">{formatTokens(session.total_tokens)}</span>
        <span className="token-total-label">tokens en esta sesión</span>
      </div>

      <dl className="token-breakdown">
        <div className="token-row">
          <dt>Entrada</dt>
          <dd>{formatTokens(session.prompt_tokens)}</dd>
        </div>
        <div className="token-row">
          <dt>Salida</dt>
          <dd>{formatTokens(session.completion_tokens)}</dd>
        </div>
        <div className="token-row">
          <dt>Consultas</dt>
          <dd>{requests}</dd>
        </div>
      </dl>

      <div className="panel-header panel-header-sub">
        <span className="panel-kicker">Última respuesta</span>
      </div>
      {last ? (
        <dl className="token-breakdown">
          <div className="token-row">
            <dt>Entrada</dt>
            <dd>{formatTokens(last.prompt_tokens)}</dd>
          </div>
          <div className="token-row">
            <dt>Salida</dt>
            <dd>{formatTokens(last.completion_tokens)}</dd>
          </div>
          <div className="token-row token-row-strong">
            <dt>Total</dt>
            <dd>{formatTokens(last.total_tokens)}</dd>
          </div>
        </dl>
      ) : (
        <p className="panel-empty">Aún no hay consultas en esta sesión.</p>
      )}
    </aside>
  );
}

export function ChatWindow({ projectId }: { projectId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [indexedSources, setIndexedSources] = useState<IndexedSource[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sessionUsage, setSessionUsage] = useState<TokenUsage>(EMPTY_USAGE);
  const [lastUsage, setLastUsage] = useState<TokenUsage | null>(null);
  const [requestCount, setRequestCount] = useState(0);
  const [conversationId] = useState(() => loadConversationId(projectId));

  const loadSources = useCallback(() => {
    setSourcesLoading(true);
    listSources(projectId)
      .then(setIndexedSources)
      .catch(() => setIndexedSources([]))
      .finally(() => setSourcesLoading(false));
  }, [projectId]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  function updateMessage(id: string, patch: Partial<ChatMessage>) {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? ({ ...m, ...patch } as ChatMessage) : m)),
    );
  }

  const { upload, addUrl } = useUpload({
    projectId,
    onUpdate: (id, patch) => {
      updateMessage(id, {
        status: patch.status as AttachmentStatus | undefined,
        chunkCount: patch.chunkCount,
        error: patch.error,
        jobId: patch.jobId,
      } as Partial<ChatMessage>);
      if (patch.status === "ready") loadSources();
    },
  });

  async function handleDeleteSource(sourceId: string) {
    try {
      await deleteSource(projectId, sourceId);
      setIndexedSources((prev) => prev.filter((s) => s.source_id !== sourceId));
    } catch (err) {
      window.alert(err instanceof Error ? err.message : String(err));
    }
  }

  const { ask } = useChatStream({
    projectId,
    sessionId: conversationId,
    onSources: (id, sources: SourceCitation[]) => updateMessage(id, { sources }),
    onMemory: (id, memory: MemoryInfo) => updateMessage(id, { memory } as Partial<ChatMessage>),
    onToken: (id, token) =>
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id && m.role === "assistant"
            ? { ...m, text: m.text + token }
            : m,
        ),
      ),
    onUsage: (_id, usage: TokenUsage) => {
      setLastUsage(usage);
      setRequestCount((count) => count + 1);
      setSessionUsage((prev) => ({
        prompt_tokens: prev.prompt_tokens + usage.prompt_tokens,
        completion_tokens: prev.completion_tokens + usage.completion_tokens,
        total_tokens: prev.total_tokens + usage.total_tokens,
      }));
    },
    onDone: (id) => updateMessage(id, { streaming: false } as Partial<ChatMessage>),
    onError: (id, error) =>
      updateMessage(id, { streaming: false, text: `⚠️ ${error.message}` } as Partial<ChatMessage>),
  });

  function handleFilesSelected(files: File[]) {
    for (const file of files) {
      const id = newId();
      setMessages((prev) => [
        ...prev,
        {
          id,
          role: "user",
          kind: "attachment",
          fileName: file.name,
          jobId: "",
          status: "processing",
        },
      ]);
      void upload(id, file);
    }
  }

  function handleUrlSubmit(event: React.FormEvent) {
    event.preventDefault();
    const url = urlInput.trim();
    if (!url) return;
    setUrlInput("");

    const id = newId();
    setMessages((prev) => [
      ...prev,
      {
        id,
        role: "user",
        kind: "attachment",
        fileName: url,
        jobId: "",
        status: "processing",
      },
    ]);
    void addUrl(id, url);
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question) return;

    const userMessageId = newId();
    const assistantMessageId = newId();
    setInput("");

    setMessages((prev) => [
      ...prev,
      { id: userMessageId, role: "user", kind: "text", text: question },
      {
        id: assistantMessageId,
        role: "assistant",
        kind: "text",
        text: "",
        sources: [],
        streaming: true,
      } satisfies AssistantMessage,
    ]);

    void ask(assistantMessageId, question);
  }

  return (
    <div className="chat-window">
      <aside className="chat-panel chat-panel-left" aria-label="Adjuntos y enlaces">
        <div className="panel-header">
          <span className="panel-kicker">Proyecto</span>
          <h2 className="panel-title">Adjuntos y enlaces</h2>
        </div>

        <section className="panel-section">
          <div className="panel-section-label">Fuentes indexadas</div>
          {sourcesLoading ? (
            <p className="panel-empty">Cargando fuentes indexadas…</p>
          ) : indexedSources.length === 0 ? (
            <p className="panel-empty">
              Aún no hay archivos indexados en este proyecto.
            </p>
          ) : (
            <ul className="source-list">
              {indexedSources.map((source) => (
                <li key={source.source_id} className="source-item">
                  <span className="source-item-title">
                    {source.title ?? source.source_id}
                  </span>
                  <span className="source-item-meta">
                    {source.chunk_count} fragmentos
                  </span>
                  <button
                    type="button"
                    className="indexed-source-delete"
                    title="Eliminar adjunto"
                    aria-label={`Eliminar ${source.source_id}`}
                    onClick={() => handleDeleteSource(source.source_id)}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel-section">
          <div className="panel-section-label">Añadir enlace</div>
          <form className="url-form" onSubmit={handleUrlSubmit}>
            <input
              className="url-input"
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="URL o repo Git (GitHub, GitLab…)"
            />
            <button type="submit" className="url-button">
              Añadir
            </button>
          </form>
        </section>
      </aside>

      <div className="chat-main">
        <div className="message-list">
          {messages.length === 0 && (
            <div className="empty-state">
              <EmptyStateIcon />
              <div className="empty-state-title">La sala está en blanco</div>
              <p className="empty-state-hint">
                Adjunta un documento, imagen, audio o video y pregúntale algo sobre su contenido.
              </p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <UploadDropzone onFilesSelected={handleFilesSelected}>
            <input
              className="composer-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Escribe tu pregunta..."
            />
          </UploadDropzone>
          <button type="submit" className="send-button">
            Enviar
            <SendIcon />
          </button>
        </form>
      </div>

      <TokenCounter session={sessionUsage} last={lastUsage} requests={requestCount} />
    </div>
  );
}
