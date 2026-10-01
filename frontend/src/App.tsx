import { useEffect, useState } from "react";
import { ChatWindow } from "./components/ChatWindow";
import { ProjectSelector } from "./components/ProjectSelector";
import { createProject, loadProjects, saveProjects } from "./projects";
import "./styles.css";

export default function App() {
  const [projects, setProjects] = useState(loadProjects);
  const [selectedProjectId, setSelectedProjectId] = useState(projects[0]?.id ?? "");

  useEffect(() => {
    saveProjects(projects);
  }, [projects]);

  function handleAddProject(name: string) {
    const project = createProject(name);
    setProjects((prev) => [...prev, project]);
    setSelectedProjectId(project.id);
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand-kicker">Sistema de recuperación aumentada</span>
        <h1>
          RAG <em>Lab</em>
        </h1>
      </header>
      <ProjectSelector
        projects={projects}
        selectedId={selectedProjectId}
        onSelect={setSelectedProjectId}
        onAdd={handleAddProject}
      />
      <ChatWindow key={selectedProjectId} projectId={selectedProjectId} />
    </div>
  );
}
