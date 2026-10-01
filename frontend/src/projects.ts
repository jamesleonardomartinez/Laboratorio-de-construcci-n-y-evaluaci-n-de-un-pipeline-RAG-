export interface Project {
  id: string;
  name: string;
}

export const PROJECTS: Project[] = [
  { id: "proyecto-1", name: "Proyecto 1" },
  { id: "proyecto-2", name: "Proyecto 2" },
  { id: "proyecto-3", name: "Proyecto 3" },
  { id: "proyecto-4", name: "Proyecto 4" },
  { id: "proyecto-5", name: "Proyecto 5" },
];

const STORAGE_KEY = "rag-lab.projects";

export function createProject(name: string): Project {
  return { id: crypto.randomUUID(), name };
}

export function loadProjects(): Project[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return PROJECTS;
    const parsed: unknown = JSON.parse(raw);
    if (
      Array.isArray(parsed) &&
      parsed.length > 0 &&
      parsed.every(
        (p) =>
          p !== null &&
          typeof p === "object" &&
          typeof (p as Project).id === "string" &&
          typeof (p as Project).name === "string",
      )
    ) {
      return parsed as Project[];
    }
  } catch {
    // ignore missing/corrupt storage
  }
  return PROJECTS;
}

export function saveProjects(projects: Project[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  } catch {
    // ignore quota/unavailable storage
  }
}
