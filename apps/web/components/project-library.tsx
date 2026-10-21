"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type {
  BuildMode,
  ProjectDocument,
  ProjectSummary,
} from "@pptx/contracts";
import { api, message } from "@/lib/api";

export function ProjectLibrary() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("My presentation");
  const [mode, setMode] = useState<BuildMode>("fidelity");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    api<{ projects: ProjectSummary[] }>("/projects", { signal: abort.signal })
      .then((data) => setProjects(data.projects))
      .catch((error) => {
        if (!abort.signal.aborted) setError(message(error));
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const doc = await api<ProjectDocument>("/projects", {
        method: "POST",
        body: JSON.stringify({ name, mode }),
      });
      router.push(`/projects/${doc.project.id}/slides/${doc.slides[0].number}`);
    } catch (error) {
      setError(message(error));
      setBusy(false);
    }
  }

  return (
    <main className="library">
      <header className="library-header">
        <span className="brand-mark">S</span>
        <strong>Slide Studio</strong>
        <span className="muted">Your content, right where it belongs.</span>
      </header>
      <div className="library-intro">
        <span className="eyebrow">WORKSPACE</span>
        <h1>
          Your ideas,
          <br />
          your voice.
        </h1>
        <p>
          Open a presentation, edit text on the slide and export to PowerPoint.
        </p>
      </div>
      <section className="library-grid">
        <form className="create-card" onSubmit={create}>
          <span className="eyebrow">GET STARTED</span>
          <h2>New presentation</h2>
          <label htmlFor="project-name">Project name</label>
          <input
            id="project-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            required
            disabled={busy}
          />
          <label htmlFor="project-mode">Presentation template</label>
          <select
            id="project-mode"
            value={mode}
            onChange={(e) => setMode(e.target.value as BuildMode)}
            disabled={busy}
          >
            <option value="fidelity">Original presentation · 71 slides</option>
            <option value="responsive">Adaptive templates · 7 slides</option>
          </select>
          <p className="small muted">
            An independent copy with its own edit history.
          </p>
          <button className="primary" disabled={busy || !name.trim()}>
            {busy ? "Preparing presentation…" : "Create presentation →"}
          </button>
        </form>
        <div className="project-list">
          <div className="section-heading">
            <h2>Your projects</h2>
            <span className="count">{projects.length}</span>
          </div>
          {loading ? (
            <p className="muted">Loading projects…</p>
          ) : projects.length === 0 ? (
            <div className="empty-state">
              <span>↗</span>
              <h3>A space for your next ideas.</h3>
              <p>Your saved projects will appear here.</p>
            </div>
          ) : (
            projects.map((project) => (
              <Link
                className="project-row"
                key={project.id}
                href={`/projects/${project.id}`}
              >
                <span className="project-icon">▤</span>
                <div>
                  <strong>{project.name}</strong>
                  <p>
                    {project.mode === "fidelity" ? "Original" : "Adaptive"} ·{" "}
                    {new Date(project.updatedAt).toLocaleDateString("en")}
                  </p>
                </div>
                <span>→</span>
              </Link>
            ))
          )}
        </div>
      </section>
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
    </main>
  );
}
