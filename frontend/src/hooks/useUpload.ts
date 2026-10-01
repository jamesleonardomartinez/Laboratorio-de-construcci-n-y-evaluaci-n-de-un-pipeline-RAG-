import { useCallback } from "react";
import { getStatus, ingestUrl as ingestUrlRequest, uploadFile } from "../api";
import type { AttachmentStatus } from "../types";

const POLL_INTERVAL_MS = 1500;

interface UseUploadOptions {
  projectId: string;
  onUpdate: (
    messageId: string,
    patch: { jobId?: string; status?: AttachmentStatus; chunkCount?: number; error?: string },
  ) => void;
}

// GitHub/GitLab/Bitbucket repo URLs (and git@ / *.git) are ingested as a Git
// repository; anything else is fetched as a web page.
export function detectSourceType(raw: string): string {
  const trimmed = raw.trim();
  if (trimmed.startsWith("git@") || trimmed.endsWith(".git")) return "repo";
  try {
    const url = new URL(trimmed);
    const host = url.hostname.toLowerCase();
    if (["github.com", "gitlab.com", "bitbucket.org"].includes(host)) {
      const parts = url.pathname.replace(/\.git$/, "").split("/").filter(Boolean);
      if (parts.length === 2) return "repo";
    }
  } catch {
    // not a URL: let the backend decide
  }
  return "url";
}

export function useUpload({ projectId, onUpdate }: UseUploadOptions) {
  const upload = useCallback(
    async (messageId: string, file: File) => {
      try {
        const { job_id: jobId } = await uploadFile(projectId, file);
        onUpdate(messageId, { jobId, status: "processing" });
        await pollUntilDone(projectId, jobId, messageId, onUpdate);
      } catch (err) {
        onUpdate(messageId, {
          status: "failed",
          error: err instanceof Error ? err.message : String(err),
        });
      }
    },
    [projectId, onUpdate],
  );

  const addUrl = useCallback(
    async (messageId: string, url: string) => {
      try {
        const { job_id: jobId } = await ingestUrlRequest(projectId, url, detectSourceType(url));
        onUpdate(messageId, { jobId, status: "processing" });
        await pollUntilDone(projectId, jobId, messageId, onUpdate);
      } catch (err) {
        onUpdate(messageId, {
          status: "failed",
          error: err instanceof Error ? err.message : String(err),
        });
      }
    },
    [projectId, onUpdate],
  );

  return { upload, addUrl };
}

async function pollUntilDone(
  projectId: string,
  jobId: string,
  messageId: string,
  onUpdate: UseUploadOptions["onUpdate"],
): Promise<void> {
  while (true) {
    const status = await getStatus(projectId, jobId);
    if (status.status === "completed") {
      onUpdate(messageId, { status: "ready", chunkCount: status.chunk_count });
      return;
    }
    if (status.status === "failed") {
      onUpdate(messageId, { status: "failed", error: status.error ?? "Ingestion failed" });
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}
