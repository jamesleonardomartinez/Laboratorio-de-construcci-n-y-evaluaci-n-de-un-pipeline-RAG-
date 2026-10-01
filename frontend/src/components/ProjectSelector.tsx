import { useRef, useState } from "react";
import type { Project } from "../projects";

interface ProjectSelectorProps {
  projects: Project[];
  selectedId: string;
  onSelect: (id: string) => void;
  onAdd: (name: string) => void;
}

export function ProjectSelector({ projects, selectedId, onSelect, onAdd }: ProjectSelectorProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [name, setName] = useState("");
  const settledRef = useRef(false);

  function openAdd() {
    settledRef.current = false;
    setName("");
    setIsAdding(true);
  }

  function close() {
    settledRef.current = true;
    setName("");
    setIsAdding(false);
  }

  function commit() {
    if (settledRef.current) return;
    settledRef.current = true;
    const trimmed = name.trim();
    if (trimmed) onAdd(trimmed);
    setName("");
    setIsAdding(false);
  }

  return (
    <div className="project-selector" role="group" aria-label="Seleccionar proyecto">
      {projects.map((project) => (
        <button
          key={project.id}
          type="button"
          className={`project-option ${project.id === selectedId ? "selected" : ""}`}
          aria-pressed={project.id === selectedId}
          onClick={() => onSelect(project.id)}
        >
          {project.name}
        </button>
      ))}

      {isAdding ? (
        <input
          className="project-add-input"
          type="text"
          autoFocus
          value={name}
          placeholder="Nombre del proyecto"
          aria-label="Nombre del nuevo proyecto"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") close();
          }}
          onBlur={commit}
        />
      ) : (
        <button
          type="button"
          className="project-add-button"
          aria-label="Agregar proyecto"
          title="Agregar proyecto"
          onClick={openAdd}
        >
          + Nuevo
        </button>
      )}
    </div>
  );
}
