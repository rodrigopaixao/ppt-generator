# Inline slide editor

[Documentation index](README.md)

The editor is an npm workspace application: a Next.js App Router frontend in
`apps/web`, a Node.js/AdonisJS API in `apps/api`, and shared TypeScript contracts
in `packages/contracts`. The existing generator commands remain available.

## Run locally

Requirements: Node.js **24 or later**, npm, Python 3, and the reference PPTX in
the repository root. For complete slide backgrounds, install **LibreOffice**
(`soffice`) and **Poppler** (`pdftoppm`) on the API host. Install the chart-label extraction dependency with
`python3 -m pip install -r requirements-editor.txt`. Basic shape and table editing
works without this optional package. Install the presentation's fonts on the
API host and browser host for closer visual matching.

```sh
nvm use
npm ci
npm run dev
```

Open [Slide Studio](http://127.0.0.1:3000). Next.js proxies `/api/*` to AdonisJS at
`http://127.0.0.1:3333`; the browser uses one origin. API controllers and routes
live in AdonisJS, not in Next.js route handlers.

Optional configuration: copy `apps/api/.env.example` to `apps/api/.env`, and
`apps/web/.env.example` to `apps/web/.env.local`. The defaults work without these
files. `API_URL` is read by Next.js when compiling its proxy configuration; set
it at build time as well as during development.

| Setting           | Default                           | Purpose                               |
| ----------------- | --------------------------------- | ------------------------------------- |
| `HOST`, `PORT`    | `127.0.0.1`, `3333`               | AdonisJS listener                     |
| `EDITOR_DATA_DIR` | `.editor-data/` in the repository | Persistent project files              |
| `REPO_ROOT`       | Discovered repository root        | Generator code, content and reference |
| `PYTHON`          | `python3`                         | DrawingML adapter runtime             |
| `SOFFICE_BIN`     | `soffice` from PATH               | LibreOffice executable                |
| `PDFTOPPM_BIN`    | `pdftoppm` from PATH              | Poppler executable                    |
| `API_URL` (web)   | `http://127.0.0.1:3333`           | Next.js proxy destination             |

## Routes and interactions

- `/`: create a project or reopen a saved project.
- `/projects/[projectId]`: open the first slide for the selected project mode.
- `/projects/[projectId]/slides/[slideNumber]`: edit a particular source slide.

The original mode exposes all 71 source slides. The responsive mode exposes
source slides 5, 10, 21, 38, 50, 64 and 68. Source numbers remain stable when
navigating or exporting; hidden slides retain their hidden state in the PPTX.
The editor intentionally uses fidelity without the quality profile: quality
repair recipes can replace content and add continuations, and are not part of
this editing contract.

Double-click a text box or table cell, or focus it with Tab and press Enter. Text
updates immediately in place. Enter commits titles (Shift+Enter inserts a line break); Enter inserts line breaks
in paragraphs. Ctrl/Cmd+Enter or clicking outside commits either kind. Escape
and Cancel discard the current editing session. Paste uses plain text only.
Drag, navigation and document actions wait until the current edit is committed
or cancelled. Undo/redo is available in the toolbar and with Ctrl/Cmd+Z,
Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y outside the text editor. During typing, the
browser's text undo remains local to the editor.

Uncommitted drafts are stored locally per project/slide/element. If saving
fails, the editor retains the draft. After a reload, “Recover draft” reopens
it. A revision conflict requires reloading the project, reviewing the draft,
and explicitly saving it again. Reloading does not automatically overwrite
another tab's changes.

## Rendering and content ownership

Each project stores an immutable `base.pptx`, baseline scenes, text overrides,
a revision, and edit history. The reference PPTX and extracted data are not
modified by editing or export. Native IDs use the source slide number and
DrawingML ID (`5.e5`); responsive IDs use Canvas semantic names such as
`50.pillars.items.0.title`.

`scripts/editor_scene.py` resolves geometry and basic typography from DrawingML,
including theme font/color references, placeholder inheritance, and nested group
transforms. Shape text, inherited layout/master labels, and individual native table cells are editable, including
mixed formatting, bullets, hyperlinks, fields, and rotated or reflected text.
Merged cells expose their anchor once, with the complete merged geometry; empty
cells are also editable. Table IDs append `/cell/row/column` to the owner ID.
Rendered chart text, including titles, legends, category labels, data labels and
automatic axis ticks, is measured on demand with LibreOffice and `pdfplumber`.
Labels use stable per-chart IDs ending in `/chart-text/index`; repeated values
remain separate targets. Rotated axis titles retain their orientation. The scene
index and geometry cache are shared by reopening, history and export. If extraction
fails, existing native chart labels remain visible and the editor reports the
missing dependency. Text embedded in pictures still requires OCR and background
reconstruction and is not editable by this adapter.

`scripts/editor_text.py` applies character-based edits while retaining unchanged
run formatting, paragraph properties, hyperlinks and component structure. New text
inherits adjacent formatting. An edited automatic field becomes literal text;
untouched fields retain their behavior. Inherited label edits clone the owning layout/master chain for that slide so shared templates remain unchanged. Table edits preserve fills, borders,
merges and sibling cells. Responsive tables receive cell overrides before font
fitting and row measurement. Existing projects automatically rebuild outdated
scene indexes; preview and background caches are versioned.

For each requested slide, a separate temporary deck clears editable shape and cell text and
selects that slide. LibreOffice and Poppler render it to a cached PNG. Browser
text overlays supply the editable content. Noneditable objects remain in the
background. Without the rendering executables, the editor explicitly shows a
simplified text preview; saving and PowerPoint export still work.

Browser overlays approximate Office typography: installed fonts, line breaking,
text effects and z-order may differ. This is a text editing preview, not an
Office-compatible rendering engine. Overflow is highlighted rather than
silently discarding text. Fidelity preserves source boxes. Responsive mode
regenerates a preview after each committed revision to resolve font fitting and
geometry; stale client requests are discarded. A failed fit preserves the saved
text, displays the problem and causes export to fail without losing edits.

A text edit on a chart changes display text, not series values. On export, only
edited charts are isolated: their native labels become transparent, and all labels
of that chart are emitted as independently editable PowerPoint text boxes in their
measured positions. Chart geometry, series, category caches and embedded workbooks
remain intact. Those literal label boxes no longer update automatically when chart
data changes later in PowerPoint. Unedited charts retain their original native
labels. This also permits arbitrary text for automatic ticks without modifying data.

PptxGenJS 4's duplicate table IDs are normalized on responsive decks produced
through the API. Semantic element names remain unchanged.

## API contract

All paths are under `/api`. Errors contain `error` and `code`.

| Method and path                                          | Result                                                         |
| -------------------------------------------------------- | -------------------------------------------------------------- |
| `GET /health`                                            | API availability                                               |
| `GET /projects`                                          | Saved project summaries                                        |
| `POST /projects`                                         | Create `{name, mode: "fidelity" \| "responsive"}`; returns 201 |
| `GET /projects/:id`                                      | Project, history and slide summaries                           |
| `GET /projects/:id/slides/:number?revision=N`            | Scene for a document revision                                  |
| `PATCH /projects/:id/slides/:number/text`                | Commit `{revision, elementId, text}`                           |
| `POST /projects/:id/history`                             | Apply `{revision, direction: "undo" \| "redo"}`                |
| `GET /projects/:id/slides/:number/background?revision=N` | Cached PNG background                                          |
| `POST /projects/:id/exports`                             | Queue an immutable revision snapshot; returns 202              |
| `GET /projects/:id/exports/:jobId`                       | Export status                                                  |
| `GET /projects/:id/exports/:jobId/download`              | Download completed PPTX                                        |

The API validates element eligibility, text size/control characters, project
identity and revision. Mutations with an old revision return 409. A text edit
preserves other generator properties because the API writes only its own text
override map. Empty strings are valid edits. The history's redo branch is
discarded after a new edit following undo.

Persistence uses atomic JSON replacement and a per-project mutation queue.
Generator subprocesses keep PPTX work out of AdonisJS's event loop. Exports are
serialized and take a revision snapshot before queuing, so later edits cannot
enter an in-progress export. Export jobs survive as records; interrupted jobs
are reported as failed after API restart and can be requested again.

This implementation targets a **local, single-process workspace**. It has no
user authentication, project authorization or distributed locking. Keep the
default loopback listener for local use. A shared deployment needs those
features plus a database/shared job queue. Persist `EDITOR_DATA_DIR` across API
restarts; generated backgrounds, previews and exports currently require manual
disk retention management.

## Build and verify

```sh
npm run typecheck
npm run test:editor
npm test
npm exec -- playwright install chromium
npm run test:e2e
npm run build:apps
```

The end-to-end tests launch isolated API/web servers on ports 3344/3100 and
store artifacts under `output/editor-e2e`. They exercise typing, cancellation,
history, draft recovery, paragraph paste, table cell editing, revision conflicts, adaptive previews
and the actual text inside exported native/responsive PPTX packages. Complete
background verification requires the preview executables above.

Run compiled applications in two terminals after `npm run build:apps`:

```sh
npm run start -w @pptx/api
npm run start -w @pptx/web
```

The compiled API still requires access to this repository's generator, assets,
Python scripts and source content. It is not a standalone generator bundle.
