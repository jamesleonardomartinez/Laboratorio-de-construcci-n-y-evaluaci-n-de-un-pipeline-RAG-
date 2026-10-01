import { useRef, useState } from "react";
import type { DragEvent, ChangeEvent } from "react";

function PaperclipIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path
        d="M17.5 8.5 9.4 16.6a3 3 0 1 1-4.24-4.24l8.48-8.48a4.5 4.5 0 1 1 6.36 6.36L11.5 18.7a2 2 0 1 1-2.83-2.83l7.07-7.07"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface UploadDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  children: React.ReactNode;
}

export function UploadDropzone({ onFilesSelected, children }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) onFilesSelected(files);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length > 0) onFilesSelected(files);
    event.target.value = "";
  }

  return (
    <div
      className={`dropzone ${isDragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <button
        type="button"
        className="attach-button"
        aria-label="Adjuntar archivo"
        onClick={() => inputRef.current?.click()}
      >
        <PaperclipIcon />
      </button>
      <input ref={inputRef} type="file" hidden onChange={handleInputChange} />
      {children}
    </div>
  );
}
