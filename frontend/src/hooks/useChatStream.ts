import { useCallback } from "react";
import { streamChat } from "../api";
import type { MemoryInfo, SourceCitation, TokenUsage } from "../types";

interface UseChatStreamOptions {
  projectId: string;
  sessionId: string;
  onToken: (messageId: string, token: string) => void;
  onSources: (messageId: string, sources: SourceCitation[]) => void;
  onMemory: (messageId: string, memory: MemoryInfo) => void;
  onUsage: (messageId: string, usage: TokenUsage) => void;
  onDone: (messageId: string) => void;
  onError: (messageId: string, error: Error) => void;
}

export function useChatStream({
  projectId,
  sessionId,
  onToken,
  onSources,
  onMemory,
  onUsage,
  onDone,
  onError,
}: UseChatStreamOptions) {
  const ask = useCallback(
    async (messageId: string, question: string) => {
      await streamChat(projectId, sessionId, question, {
        onSources: (sources) => onSources(messageId, sources),
        onMemory: (memory) => onMemory(messageId, memory),
        onToken: (token) => onToken(messageId, token),
        onUsage: (usage) => onUsage(messageId, usage),
        onDone: () => onDone(messageId),
        onError: (error) => onError(messageId, error),
      });
    },
    [projectId, sessionId, onToken, onSources, onMemory, onUsage, onDone, onError],
  );

  return { ask };
}
