import { mkdir, readFile, rename, readdir, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import type {
  EditOperation,
  Project,
  ProjectSummary,
  SlideScene,
} from "@pptx/contracts";
import { EditorError } from "./errors.js";

export class ProjectStore {
  private locks = new Map<string, Promise<unknown>>();
  constructor(public directory: string) {}

  path(id: string) {
    if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/.test(id))
      throw new EditorError(404, "Project not found.", "NOT_FOUND");
    return join(this.directory, id);
  }

  async read(id: string): Promise<Project> {
    try {
      return JSON.parse(
        await readFile(join(this.path(id), "project.json"), "utf8"),
      );
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT")
        throw new EditorError(404, "Project not found.", "NOT_FOUND");
      throw error;
    }
  }

  async write(project: Project) {
    const directory = this.path(project.id);
    await mkdir(directory, { recursive: true });
    const temporary = join(directory, `${randomUUID()}.tmp`);
    await writeFile(temporary, JSON.stringify(project), "utf8");
    await rename(temporary, join(directory, "project.json"));
  }

  async list(): Promise<ProjectSummary[]> {
    await mkdir(this.directory, { recursive: true });
    const entries = await readdir(this.directory, { withFileTypes: true });
    const loaded = await Promise.all(
      entries
        .filter((e) => e.isDirectory() && /^[0-9a-f-]{36}$/.test(e.name))
        .map(async (e) => {
          try {
            return await this.read(e.name);
          } catch (error) {
            if (error instanceof EditorError && error.code === "NOT_FOUND")
              return null;
            throw error;
          }
        }),
    );
    const projects = loaded.filter((p): p is Project => p !== null);
    return projects
      .map(({ id, name, mode, revision, updatedAt }) => ({
        id,
        name,
        mode,
        revision,
        updatedAt,
      }))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }

  async mutate(
    id: string,
    revision: number,
    fn: (project: Project) => void,
  ): Promise<Project> {
    const previous = this.locks.get(id) || Promise.resolve();
    const pending = previous
      .catch(() => {})
      .then(async () => {
        const project = await this.read(id);
        if (!Number.isInteger(revision) || revision !== project.revision) {
          throw new EditorError(
            409,
            "This project was updated in another tab. Reload before saving.",
            "REVISION_CONFLICT",
          );
        }
        fn(project);
        project.revision++;
        project.updatedAt = new Date().toISOString();
        await this.write(project);
        return project;
      });
    this.locks.set(id, pending);
    try {
      return await pending;
    } finally {
      if (this.locks.get(id) === pending) this.locks.delete(id);
    }
  }

  async edit(
    id: string,
    revision: number,
    scene: SlideScene,
    elementId: string,
    text: unknown,
  ) {
    const element = scene.elements.find((e) => e.id === elementId);
    if (!element?.editable)
      throw new EditorError(
        422,
        "This text element is not available on the slide.",
        "NOT_EDITABLE",
      );
    if (
      typeof text !== "string" ||
      text.length > 20_000 ||
      /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(text)
    ) {
      throw new EditorError(
        422,
        "Text is invalid or exceeds 20,000 characters.",
        "INVALID_TEXT",
      );
    }
    const normalized = text.replace(/\r\n?/g, "\n");
    return this.mutate(id, revision, (project) => {
      const key = `${scene.number}.${elementId}`;
      const before = project.overrides[key] ?? element.originalText;
      if (before === normalized) return;
      const operation: EditOperation = {
        slideNumber: scene.number,
        elementId,
        before,
        after: normalized,
      };
      project.history = project.history.slice(0, project.cursor);
      project.history.push(operation);
      project.cursor = project.history.length;
      this.setOverride(project, key, normalized, element.originalText);
    });
  }

  private setOverride(
    project: Project,
    key: string,
    value: string,
    original: string,
  ) {
    if (value === original) delete project.overrides[key];
    else project.overrides[key] = value;
  }

  async history(
    id: string,
    revision: number,
    direction: "undo" | "redo",
    scenes: SlideScene[],
  ) {
    return this.mutate(id, revision, (project) => {
      const index = direction === "undo" ? project.cursor - 1 : project.cursor;
      const op = project.history[index];
      if (!op)
        throw new EditorError(422, "No edit available.", "EMPTY_HISTORY");
      const element = scenes
        .find((s) => s.number === op.slideNumber)
        ?.elements.find((e) => e.id === op.elementId);
      if (!element)
        throw new EditorError(
          422,
          "History element not found.",
          "NOT_EDITABLE",
        );
      this.setOverride(
        project,
        `${op.slideNumber}.${op.elementId}`,
        direction === "undo" ? op.before : op.after,
        element.originalText,
      );
      project.cursor += direction === "undo" ? -1 : 1;
    });
  }
}
