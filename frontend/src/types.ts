export type AttachmentStatus = "processing" | "ready" | "failed";

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface SourceCitation {
  source_id: string;
  section: string | null;
  modality?: "text" | "image";
}

export interface MemoryInfo {
  count: number;
  items: string[];
}

export interface UserTextMessage {
  id: string;
  role: "user";
  kind: "text";
  text: string;
}

export interface AttachmentMessage {
  id: string;
  role: "user";
  kind: "attachment";
  fileName: string;
  jobId: string;
  status: AttachmentStatus;
  chunkCount?: number;
  error?: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  kind: "text";
  text: string;
  sources: SourceCitation[];
  memory?: MemoryInfo;
  streaming: boolean;
}

export type ChatMessage = UserTextMessage | AttachmentMessage | AssistantMessage;

export interface IndexedSource {
  source_id: string;
  source_type: string;
  title: string | null;
  chunk_count: number;
}
