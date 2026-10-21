"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import type { SlideScene, TextElement } from "@pptx/contracts";
import { api, message } from "@/lib/api";
import { useEditor } from "./editor-workspace";

export function SlideEditor({ slideNumber }: { slideNumber: number }) {
  const { project, slides, editing, busy, setEditing } = useEditor();
  const [scene, setScene] = useState<SlideScene | null>(null);
  const [error, setError] = useState("");
  const [background, setBackground] = useState<"loading" | "ready" | "failed">(
    "loading",
  );
  const [zoom, setZoom] = useState(100);
  const [width, setWidth] = useState(900);
  const [overflows, setOverflows] = useState<string[]>([]);
  const viewport = useRef<HTMLDivElement>(null);
  const index = slides.findIndex((s) => s.number === slideNumber);

  // Browser Back can leave a slide without triggering its navigation guard.
  // Its draft is already local; release the workspace's editing state.
  useEffect(() => () => setEditing(false), [setEditing]);

  useEffect(() => {
    const abort = new AbortController();
    api<SlideScene>(
      `/projects/${project.id}/slides/${slideNumber}?revision=${project.revision}`,
      { signal: abort.signal },
    )
      .then(setScene)
      .catch((error) => {
        if (!abort.signal.aborted) setError(message(error));
      });
    return () => abort.abort();
  }, [project.id, project.revision, slideNumber]);

  const backgroundRevision =
    project.mode === "responsive" ? project.revision : 0;
  useEffect(() => {
    setBackground("loading");
  }, [backgroundRevision]);

  useEffect(() => {
    if (!viewport.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    observer.observe(viewport.current);
    return () => observer.disconnect();
  }, [scene]);

  const reportOverflow = useCallback((id: string, overflowing: boolean) => {
    setOverflows((old) =>
      overflowing
        ? old.includes(id)
          ? old
          : [...old, id]
        : old.includes(id)
          ? old.filter((value) => value !== id)
          : old,
    );
  }, []);

  if (error)
    return (
      <div className="loading-state" role="alert">
        {error}
      </div>
    );
  if (!scene) return <p className="loading-state">Loading slide…</p>;
  const scale = (Math.min((width - 48) / (scene.width * 96), 1) * zoom) / 100;
  const currentTitle = scene.elements.find((e) => e.role === "title");
  const title = currentTitle
    ? (project.overrides[`${scene.number}.${currentTitle.id}`] ?? scene.title)
    : scene.title;

  return (
    <>
      <div className="canvas-toolbar">
        <div>
          <span className="eyebrow">
            SLIDE {String(index + 1).padStart(2, "0")} / {slides.length}
          </span>
          <h1>{title || "Untitled"}</h1>
        </div>
        <div className="zoom-control">
          <button
            aria-label="Zoom out"
            disabled={zoom <= 50 || editing}
            onClick={() => setZoom((v) => v - 25)}
          >
            −
          </button>
          <span>{zoom}%</span>
          <button
            aria-label="Zoom in"
            disabled={zoom >= 150 || editing}
            onClick={() => setZoom((v) => v + 25)}
          >
            +
          </button>
        </div>
      </div>
      <div className="canvas-viewport" ref={viewport}>
        <div
          className="canvas-positioner"
          style={{
            width: scene.width * 96 * scale,
            height: scene.height * 96 * scale,
          }}
        >
          <div
            className="slide-canvas"
            aria-label={`Slide ${slideNumber}`}
            style={{
              width: scene.width * 96,
              height: scene.height * 96,
              transform: `scale(${scale})`,
            }}
          >
            {/* Background retains component visuals with editable text removed. */}
            <img
              key={backgroundRevision}
              className="slide-background"
              src={`/api/projects/${project.id}/slides/${slideNumber}/background?schema=5&revision=${backgroundRevision}`}
              alt=""
              draggable={false}
              onLoad={() => setBackground("ready")}
              onError={() => setBackground("failed")}
            />
            {scene.elements
              .filter((element) => element.editable || background === "failed")
              .map((element) => (
                <InlineText
                  key={element.id}
                  element={element}
                  slideNumber={slideNumber}
                  onOverflow={reportOverflow}
                />
              ))}
          </div>
        </div>
      </div>
      <footer className="canvas-footer">
        <span>
          <span className="status-dot" />
          {background === "loading"
            ? "Preparing full preview…"
            : background === "failed"
              ? "Simplified preview · visuals unavailable"
              : "Full preview"}
        </span>
        <span>
          16:9 · {scene.elements.filter((e) => e.editable).length} editable text
          elements
        </span>
      </footer>
      {overflows.length > 0 && (
        <div className="overflow-notice" role="status">
          Some text exceeds its box. Review the highlighted elements before
          exporting.
          {project.mode === "responsive" &&
            " The adaptive layout is recalculated when you save."}
        </div>
      )}
      {scene.chartTextError && (
        <div className="overflow-notice" role="status">
          {scene.chartTextError}
        </div>
      )}
      {scene.layoutError && (
        <div className="overflow-notice" role="status">
          {scene.layoutError}
        </div>
      )}
      <div className="editing-guide">
        <span className="guide-icon">↖</span>
        <div>
          <strong>
            {busy
              ? "Saving your edit…"
              : editing
                ? "Your text comes to life as you type."
                : "The slide is your editing space."}
          </strong>
          <p>
            Double-click or press Enter to edit · Click outside to save · Esc to
            cancel · Ctrl/Cmd+Enter to confirm
          </p>
        </div>
      </div>
    </>
  );
}

function InlineText({
  element,
  slideNumber,
  onOverflow,
}: {
  element: TextElement;
  slideNumber: number;
  onOverflow: (id: string, value: boolean) => void;
}) {
  const { project, save, busy, editing, setEditing } = useEditor();
  const [active, setActive] = useState(false);
  const [overflow, setOverflow] = useState(false);
  const [hasDraft, setHasDraft] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const outer = useRef<HTMLDivElement>(null);
  const text = useRef<HTMLDivElement>(null);
  const draft = useRef("");
  const submitting = useRef(false);
  const activeRef = useRef(false);
  const localKey = `slide-studio:${project.id}:${slideNumber}:${element.id}`;
  const value =
    project.overrides[`${slideNumber}.${element.id}`] ?? element.originalText;
  const s = element.style;

  const measure = useCallback(() => {
    if (!text.current || !outer.current || !element.editable) return;
    const available = element.box.h * 96 - (s.margins[0] + s.margins[2]) * 96;
    const overflowing =
      text.current.scrollHeight > available + 2 ||
      text.current.scrollWidth > text.current.clientWidth + 2;
    setOverflow(overflowing);
    onOverflow(element.id, overflowing);
  }, [element.box.h, element.editable, element.id, s.margins, onOverflow]);

  useEffect(() => {
    try {
      setHasDraft(localStorage.getItem(localKey) !== null);
    } catch {}
  }, [localKey]);

  useLayoutEffect(() => {
    if (!active && text.current) renderText(text.current, element, value);
    measure();
  }, [active, value, element, measure]);

  useLayoutEffect(() => {
    if (!active || !text.current) return;
    renderText(text.current, element, draft.current);
    text.current.focus();
    const range = window.document.createRange();
    range.selectNodeContents(text.current);
    range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    measure();
  }, [active]); // Initialize DOM only when entering edit mode; typing never replaces it.

  function begin() {
    if (!element.editable || busy || editing || activeRef.current) return;
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(localKey);
    } catch {}
    draft.current = stored ?? value;
    activeRef.current = true;
    setActive(true);
    setEditing(true);
    setSaveFailed(false);
  }

  function updateDraft() {
    if (!text.current) return;
    draft.current = text.current.innerText.replace(/\r\n?/g, "\n");
    try {
      localStorage.setItem(localKey, draft.current);
    } catch {}
    setHasDraft(true);
    setSaveFailed(false);
    measure();
  }

  function finish() {
    try {
      localStorage.removeItem(localKey);
    } catch {}
    activeRef.current = false;
    setActive(false);
    setEditing(false);
    setHasDraft(false);
    setSaveFailed(false);
  }

  async function commit() {
    if (!activeRef.current || submitting.current) return;
    submitting.current = true;
    setSaving(true);
    const success =
      draft.current === value ||
      (await save(slideNumber, element.id, draft.current));
    if (success) finish();
    else setSaveFailed(true);
    submitting.current = false;
    setSaving(false);
  }

  function keyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.nativeEvent.isComposing) return;
    if (!active) {
      if (event.key === "Enter") {
        event.preventDefault();
        begin();
      }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      finish();
    } else if (
      event.key === "Enter" &&
      ((element.role === "title" && !event.shiftKey) ||
        event.ctrlKey ||
        event.metaKey)
    ) {
      event.preventDefault();
      void commit();
    }
  }

  const style: CSSProperties = {
    left: element.box.x * 96,
    top: element.box.y * 96,
    width: element.box.w * 96,
    height: element.box.h * 96,
    padding: s.margins.map((v) => `${v * 96}px`).join(" "),
    fontFamily: fontStack(s.fontFamily),
    fontSize: (s.fontSize * 96) / 72,
    color: s.color,
    fontWeight: s.bold ? 700 : 400,
    fontStyle: s.italic ? "italic" : "normal",
    textAlign: s.align,
    transform: element.transform
      ? `matrix(${element.transform.join(",")},0,0)`
      : `rotate(${element.rotation}deg)`,
    transformOrigin: element.transform ? "top left" : undefined,
    lineHeight: s.lineHeight ?? 1.1,
    justifyContent:
      s.vertical === "middle"
        ? "center"
        : s.vertical === "bottom"
          ? "flex-end"
          : "flex-start",
  };
  return (
    <div
      ref={outer}
      className={`text-element ${element.editable ? "editable" : "readonly"} ${active ? "active" : ""} ${overflow ? "overflowing" : ""}`}
      style={style}
      data-element-id={element.id}
      data-target-kind={element.target?.kind}
      onDoubleClick={begin}
    >
      <div
        ref={text}
        className="inline-text"
        contentEditable={active && !saving ? "plaintext-only" : false}
        suppressContentEditableWarning
        tabIndex={element.editable ? 0 : undefined}
        role={element.editable ? (active ? "textbox" : "button") : undefined}
        aria-label={
          element.editable
            ? `${active ? "Editing" : hasDraft ? "Continue editing" : "Edit"} ${element.name}`
            : undefined
        }
        aria-multiline={active ? true : undefined}
        onDoubleClick={begin}
        onKeyDown={keyDown}
        onInput={updateDraft}
        onBlur={() => {
          void commit();
        }}
        onDrop={(event) => {
          if (active) event.preventDefault();
        }}
        onPaste={(event) => {
          if (!active) return;
          event.preventDefault();
          const pasted = event.clipboardData.getData("text/plain");
          window.document.execCommand("insertText", false, pasted);
          updateDraft();
        }}
      />
      {active && (
        <div
          className="inline-actions"
          onMouseDown={(event) => event.preventDefault()}
        >
          <span>
            {saving
              ? "Saving…"
              : saveFailed
                ? "Save failed · draft preserved"
                : "Editing text"}
          </span>
          <button
            disabled={saving}
            onClick={() => {
              void commit();
            }}
          >
            Save
          </button>
          <button disabled={saving} onClick={finish}>
            Cancel
          </button>
        </div>
      )}
      {!active && hasDraft && (
        <button className="draft-badge" onClick={begin}>
          Recover draft
        </button>
      )}
    </div>
  );
}

/** Render trusted style properties and untrusted text through DOM APIs. */
function renderText(
  container: HTMLDivElement,
  element: TextElement,
  value: string,
) {
  container.replaceChildren();
  if (
    value !== element.text ||
    !element.paragraphs ||
    element.paragraphs
      .map((p) => p.runs.map((r) => r.text).join(""))
      .join("\n") !== value
  ) {
    container.textContent = value;
    return;
  }
  for (const paragraph of element.paragraphs) {
    const line = document.createElement("div");
    line.className = "text-paragraph";
    line.style.textAlign = paragraph.style.align;
    line.style.minHeight = "1em";
    if (paragraph.bullet) {
      line.dataset.bullet = paragraph.bullet;
      line.style.paddingLeft = `${Math.max(paragraph.marginLeft ?? 0.18, 0.18) * 96}px`;
    }
    for (const run of paragraph.runs) {
      const span = document.createElement("span");
      span.textContent = run.text;
      const style = run.style;
      Object.assign(span.style, {
        fontFamily: fontStack(style.fontFamily),
        fontSize: `${(style.fontSize * 96) / 72}px`,
        color: style.color,
        fontWeight: style.bold ? "700" : "400",
        fontStyle: style.italic ? "italic" : "normal",
        verticalAlign: style.baseline ? `${style.baseline}%` : "baseline",
        textDecoration: [
          style.underline ? "underline" : "",
          style.strike ? "line-through" : "",
        ]
          .filter(Boolean)
          .join(" "),
      });
      line.append(span);
    }
    container.append(line);
  }
}

/** Prefer a matching generic family when the Office renderer substitutes a font. */
function fontStack(family: string) {
  return /Libertine|Serif|Times|Garamond/i.test(family)
    ? `"${family}", "Times New Roman", serif`
    : /Mono|Courier/i.test(family)
      ? `"${family}", "Courier New", monospace`
      : `"${family}", Arial, sans-serif`;
}
