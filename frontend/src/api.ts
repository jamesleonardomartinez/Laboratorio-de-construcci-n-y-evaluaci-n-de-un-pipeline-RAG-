import type { IndexedSource, MemoryInfo, TokenUsage } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface UploadResponse {
  job_id: string;
  source_id: string;
  source_type: string;
  status: string;
}

export interface StatusResponse {
  job_id: string;
  source_id: string;
  source_type: string;
  status: "processing" | "completed" | "failed";
  chunk_count: number;
  error: string | null;
}

export async function uploadFile(projectId: string, file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE_URL}/projects/${projectId}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function ingestUrl(
  projectId: string,
  url: string,
  sourceType?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("url", url);
  if (sourceType) form.append("source_type", sourceType);
  const res = await fetch(`${API_BASE_URL}/projects/${projectId}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`URL ingestion failed: ${res.status}`);
  }
  return res.json();
}

export async function getStatus(projectId: string, jobId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE_URL}/projects/${projectId}/status/${jobId}`);
  if (!res.ok) {
    throw new Error(`Status check failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteSource(projectId: string, sourceId: string): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/projects/${projectId}/sources/${encodeURIComponent(sourceId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`Delete failed: ${res.status}`);
  }
}

export async function listSources(projectId: string): Promise<IndexedSource[]> {
  const res = await fetch(`${API_BASE_URL}/projects/${projectId}/sources`);
  if (!res.ok) {
    throw new Error(`Sources listing failed: ${res.status}`);
  }
  const data = await res.json();
  return data.sources ?? [];
}

export interface ChatStreamHandlers {
  onSources: (sources: { source_id: string; section: string | null }[]) => void;
  onMemory: (memory: MemoryInfo) => void;
  onToken: (token: string) => void;
  onUsage: (usage: TokenUsage) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}

export async function streamChat(
  projectId: string,
  sessionId: string,
  question: string,
  handlers: ChatStreamHandlers,
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
    if (!res.ok || !res.body) {
      throw new Error(`Chat request failed: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        handleEvent(rawEvent, handlers);
        boundary = buffer.indexOf("\n\n");
      }
    }
    handlers.onDone();
  } catch (err) {
    handlers.onError(err instanceof Error ? err : new Error(String(err)));
  }
}

function handleEvent(rawEvent: string, handlers: ChatStreamHandlers): void {
  const lines = rawEvent.split("\n");
  let eventName = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;

  const parsed = JSON.parse(data);
  if (eventName === "sources") {
    handlers.onSources(parsed.sources ?? []);
  } else if (eventName === "memory") {
    handlers.onMemory({ count: parsed.count ?? 0, items: parsed.items ?? [] });
  } else if (eventName === "token") {
    handlers.onToken(parsed.token ?? "");
  } else if (eventName === "usage") {
    handlers.onUsage({
      prompt_tokens: parsed.prompt_tokens ?? 0,
      completion_tokens: parsed.completion_tokens ?? 0,
      total_tokens: parsed.total_tokens ?? 0,
    });
  }
}
