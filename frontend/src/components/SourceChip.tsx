import type { SourceCitation } from "../types";

function DocIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M6 2h8l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
      <path d="M14 2v5h5" strokeLinejoin="round" />
    </svg>
  );
}

function ImageIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="9" cy="10" r="1.6" />
      <path d="M21 16l-5.5-5.5a2 2 0 0 0-2.8 0L4 19" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SourceChip({ source }: { source: SourceCitation }) {
  const label = source.section ? `${source.source_id} · ${source.section}` : source.source_id;
  return (
    <button type="button" className="source-chip" title={label}>
      {source.modality === "image" ? <ImageIcon /> : <DocIcon />}
      {label}
    </button>
  );
}
