"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type {
  ExportJob,
  Project,
  ProjectDocument,
  SlideSummary,
} from "@pptx/contracts";
import { api, message } from "@/lib/api";

interface EditorContext {
  project: Project;
  slides: SlideSummary[];
  busy: boolean;
  editing: boolean;
  setEditing: (value: boolean) => void;
  save: (slide: number, elementId: string, text: string) => Promise<boolean>;
}
const Context = createContext<EditorContext | null>(null);
export function useEditor() {
  const value = useContext(Context);
  if (!value) throw new Error("Editor context missing");
  return value;
}

export function EditorWorkspace({
  projectId,
  children,
}: {
  projectId: string;
  children: React.ReactNode;
}) {
  const params = useParams<{ slideNumber?: string }>();
  const [document, setDocument] = useState<ProjectDocument | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [exporting, setExporting] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      setDocument(await api<ProjectDocument>(`/projects/${projectId}`));
      setError("");
    } catch (error) {
      setError(message(error));
    }
  }, [projectId]);
  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (editing || busy) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [editing, busy]);

  const mutate = useCallback(
    async (path: string, body: object) => {
      if (!document || pending.current) return false;
      pending.current = true;
      setBusy(true);
      setError("");
      setSaved(false);
      try {
        const data = await api<{ project: Project }>(path, {
          method: path.endsWith("/text") ? "PATCH" : "POST",
          body: JSON.stringify({
            ...body,
            revision: document.project.revision,
          }),
        });
        setDocument((old) => (old ? { ...old, project: data.project } : old));
        setSaved(true);
        return true;
      } catch (error) {
        setError(message(error));
        return false;
      } finally {
        pending.current = false;
        setBusy(false);
      }
    },
    [document],
  );

  useEffect(() => {
    const keyDown = (event: KeyboardEvent) => {
      if (!document || editing || busy || !(event.ctrlKey || event.metaKey))
        return;
      const target = event.target as HTMLElement;
      if (
        target.closest(
          'input,textarea,select,[contenteditable="true"],[contenteditable="plaintext-only"]',
        )
      )
        return;
      const key = event.key.toLowerCase();
      const direction =
        key === "z"
          ? event.shiftKey
            ? "redo"
            : "undo"
          : key === "y"
            ? "redo"
            : null;
      if (!direction) return;
      event.preventDefault();
      const p = document.project;
      if (direction === "undo" ? p.cursor > 0 : p.cursor < p.history.length) {
        void mutate(`/projects/${projectId}/history`, { direction });
      }
    };
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [document, editing, busy, mutate, projectId]);

  async function exportDeck() {
    setExporting(true);
    setError("");
    setJob(null);
    try {
      let current = await api<ExportJob>(`/projects/${projectId}/exports`, {
        method: "POST",
      });
      setJob(current);
      while (
        mounted.current &&
        ["queued", "running"].includes(current.status)
      ) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        if (!mounted.current) return;
        current = await api<ExportJob>(
          `/projects/${projectId}/exports/${current.id}`,
        );
        setJob(current);
      }
      if (current.status === "failed")
        setError(current.error || "Export failed.");
    } catch (error) {
      if (mounted.current) setError(message(error));
    } finally {
      if (mounted.current) setExporting(false);
    }
  }

  if (!document)
    return (
      <main className="loading-state">
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button onClick={load}>Try again</button>
            <Link href="/">Back to projects</Link>
          </>
        ) : (
          "Opening your project…"
        )}
      </main>
    );
  const { project, slides } = document;
  const activeExport = job?.status === "complete";
  function guardNavigation(event: React.MouseEvent) {
    if (editing || pending.current) {
      event.preventDefault();
    }
  }

  return (
    <Context.Provider
      value={{
        project,
        slides,
        busy,
        editing,
        setEditing,
        save: (slide, elementId, text) =>
          mutate(`/projects/${projectId}/slides/${slide}/text`, {
            elementId,
            text,
          }),
      }}
    >
      <div className="workspace">
        <header className="editor-header">
          <Link
            href="/"
            onClick={guardNavigation}
            className="brand"
            aria-label="Back to projects"
          >
            <span className="brand-mark">S</span>
            <strong>Slide Studio</strong>
          </Link>
          <span className="header-divider" />
          <div className="document-name">
            <strong>{project.name}</strong>
            <span className="save-state" aria-live="polite">
              {busy
                ? "Saving…"
                : editing
                  ? "Editing · local draft"
                  : saved
                    ? "All changes saved"
                    : `Revision ${project.revision} · saved`}
            </span>
          </div>
          <div className="header-actions">
            <button
              aria-label="Undo"
              title="Undo last edit"
              disabled={busy || editing || project.cursor === 0}
              onClick={() =>
                mutate(`/projects/${projectId}/history`, { direction: "undo" })
              }
            >
              ↶
            </button>
            <button
              aria-label="Redo"
              title="Redo last edit"
              disabled={
                busy || editing || project.cursor === project.history.length
              }
              onClick={() =>
                mutate(`/projects/${projectId}/history`, { direction: "redo" })
              }
            >
              ↷
            </button>
            <button
              className="primary"
              disabled={busy || editing || exporting}
              onClick={exportDeck}
            >
              {exporting ? "Generating PPTX…" : "Export PowerPoint ↗"}
            </button>
            {activeExport && (
              <a
                className="download-link"
                href={`/api/projects/${projectId}/exports/${job.id}/download`}
              >
                Download r{job.revision}
              </a>
            )}
          </div>
        </header>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button onMouseDown={(e) => e.preventDefault()} onClick={load}>
              Reload project
            </button>
          </div>
        )}
        <div className="editor-body">
          <aside className="slide-sidebar">
            <div className="sidebar-heading">
              <span>SLIDES</span>
              <span>{slides.length}</span>
            </div>
            <nav aria-label="Presentation slides">
              {slides.map((slide, index) => {
                const titleOp = project.history.find(
                  (op) =>
                    op.slideNumber === slide.number &&
                    op.elementId === slide.titleElementId,
                );
                const title = slide.titleElementId
                  ? (project.overrides[
                      `${slide.number}.${slide.titleElementId}`
                    ] ??
                    titleOp?.before ??
                    slide.title)
                  : slide.title;
                return (
                  <Link
                    key={slide.number}
                    href={`/projects/${project.id}/slides/${slide.number}`}
                    onClick={guardNavigation}
                    aria-current={
                      Number(params.slideNumber) === slide.number
                        ? "page"
                        : undefined
                    }
                    className="slide-nav-item"
                  >
                    <span className="slide-index">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span>
                      <strong>{title || "Untitled"}</strong>
                      <small>
                        Slide {slide.number}
                        {slide.hidden ? " · Hidden" : ""}
                      </small>
                    </span>
                  </Link>
                );
              })}
            </nav>
            <div className="sidebar-footer">
              <span className="status-dot" />
              {project.mode === "fidelity"
                ? "Original presentation"
                : "Adaptive layout"}
            </div>
          </aside>
          <main className="editor-main">{children}</main>
        </div>
      </div>
    </Context.Provider>
  );
}
