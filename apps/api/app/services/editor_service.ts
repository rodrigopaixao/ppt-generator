import {
  copyFile,
  readdir,
  mkdir,
  readFile,
  writeFile,
  access,
  rm,
} from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import type {
  BuildMode,
  ExportJob,
  Project,
  ProjectDocument,
  SlideScene,
} from "@pptx/contracts";
import { dataRoot, repoRoot, sourcePath } from "./paths.js";
import { ProjectStore } from "./project_store.js";
import { EditorError } from "./errors.js";
import { run } from "./process.js";

export class EditorService {
  store = new ProjectStore(dataRoot);
  private backgrounds = new Map<string, Promise<string>>();
  private activeJobs = new Set<string>();
  private previews = new Map<string, Promise<string>>();
  private queue: Promise<unknown> = Promise.resolve();

  async create(name: unknown, mode: unknown): Promise<ProjectDocument> {
    if (
      typeof name !== "string" ||
      !name.trim() ||
      name.trim().length > 100 ||
      !["fidelity", "responsive"].includes(String(mode))
    ) {
      throw new EditorError(
        422,
        "Enter a valid name and mode.",
        "INVALID_PROJECT",
      );
    }
    const now = new Date().toISOString();
    const project: Project = {
      id: randomUUID(),
      name: name.trim(),
      mode: mode as BuildMode,
      revision: 0,
      createdAt: now,
      updatedAt: now,
      overrides: {},
      history: [],
      cursor: 0,
    };
    const folder = this.store.path(project.id);
    await mkdir(folder, { recursive: true });
    try {
      const base = join(folder, "base.pptx");
      if (mode === "fidelity") await copyFile(sourcePath, base);
      else {
        const config = join(folder, "baseline-config.json");
        await writeFile(
          config,
          JSON.stringify({
            theme: { fonts: { body: "Arial", heading: "Arial" } },
          }),
        );
        await run(process.execPath, [
          "src/generate.mjs",
          "--mode",
          "responsive",
          "--config",
          config,
          "--output",
          base,
        ]);
        await run(process.env.PYTHON || "python3", [
          "scripts/editor_scene.py",
          "--source",
          base,
          "--output",
          base,
          "--normalize-ids",
        ]);
      }
      await run(process.env.PYTHON || "python3", [
        "scripts/editor_scene.py",
        "--source",
        base,
        "--mode",
        project.mode,
        "--output",
        join(folder, "scenes.json"),
      ]);
      await this.store.write(project);
      return this.document(project.id);
    } catch (error) {
      await rm(folder, { recursive: true, force: true });
      throw error;
    }
  }

  async scenes(id: string): Promise<SlideScene[]> {
    await this.store.read(id);
    const file = join(this.store.path(id), "scenes.json");
    let scenes: SlideScene[] = JSON.parse(await readFile(file, "utf8"));
    if (scenes.some((scene) => scene.schemaVersion !== 5)) {
      const project = await this.store.read(id);
      await run(process.env.PYTHON || "python3", [
        "scripts/editor_scene.py",
        "--source",
        join(this.store.path(id), "base.pptx"),
        "--mode",
        project.mode,
        "--output",
        file,
      ]);
      scenes = JSON.parse(await readFile(file, "utf8"));
    }
    const chartDirectory = join(this.store.path(id), "chart-text-v5");
    const files = await readdir(chartDirectory).catch(() => [] as string[]);
    const cached = await Promise.all(
      files
        .filter((file) => /^\d+\.json$/.test(file))
        .map(
          async (file) =>
            JSON.parse(
              await readFile(join(chartDirectory, file), "utf8"),
            ) as Pick<SlideScene, "number" | "elements">,
        ),
    );
    return scenes.map((scene) => ({
      ...scene,
      elements: [
        ...scene.elements,
        ...(cached.find((value) => value.number === scene.number)?.elements ??
          []),
      ],
    }));
  }

  async document(id: string): Promise<ProjectDocument> {
    const project = await this.store.read(id);
    const scenes = await this.scenes(id);
    return {
      project,
      slides: scenes.map(({ number, title, hidden, elements }) => {
        const heading = elements.find((e) => e.role === "title");
        return {
          number,
          title: heading
            ? (project.overrides[`${number}.${heading.id}`] ?? title)
            : title,
          hidden,
          titleElementId: heading?.id,
        };
      }),
    };
  }

  async scene(id: string, number: number): Promise<SlideScene> {
    const scenes = await this.scenes(id);
    const scene = scenes.find((s) => s.number === number);
    if (!scene) throw new EditorError(404, "Slide not found.", "NOT_FOUND");
    if (
      !scene.charts?.length ||
      scene.elements.some((element) => element.target?.kind === "chartText")
    )
      return scene;
    const chartFile = join(
      this.store.path(id),
      "chart-text-v5",
      `${number}.json`,
    );
    try {
      const cached = JSON.parse(await readFile(chartFile, "utf8")) as Pick<
        SlideScene,
        "elements"
      >;
      return { ...scene, elements: [...scene.elements, ...cached.elements] };
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    const key = `chart-text:${id}.${number}`;
    let pending = this.previews.get(key);
    if (!pending) {
      pending = (async () => {
        const project = await this.store.read(id);
        const directory = join(this.store.path(id), "chart-text-v5");
        await mkdir(directory, { recursive: true });
        const output = join(directory, `${number}.json`);
        await run(process.env.PYTHON || "python3", [
          "scripts/editor_scene.py",
          "--source",
          join(this.store.path(id), "base.pptx"),
          "--mode",
          project.mode,
          "--chart-text",
          String(number),
          "--output",
          output,
        ]);
        return output;
      })();
      this.previews.set(key, pending);
    }
    try {
      const cached = JSON.parse(await readFile(await pending, "utf8")) as Pick<
        SlideScene,
        "elements"
      >;
      return { ...scene, elements: [...scene.elements, ...cached.elements] };
    } catch {
      return {
        ...scene,
        chartTextError:
          "Chart text is unavailable. Check LibreOffice and the Python pdfplumber dependency, then reload.",
      };
    } finally {
      if (this.previews.get(key) === pending) this.previews.delete(key);
    }
  }

  private async config(project: Project) {
    if (project.mode === "fidelity")
      return { source: join(this.store.path(project.id), "base.pptx") };
    const scenes = await this.scenes(project.id);
    const elements: Record<
      string,
      { text?: string; cellTexts?: Record<string, string> }
    > = {};
    for (const scene of scenes)
      for (const element of scene.elements) {
        const value = project.overrides[`${scene.number}.${element.id}`];
        if (value === undefined) continue;
        const target = element.target;
        if (target?.kind === "chartText") continue;
        const key = `${scene.number}.${target?.ownerId ?? element.id}`;
        if (target?.kind === "tableCell") {
          const options = (elements[key] ??= {});
          (options.cellTexts ??= {})[`${target.row}.${target.column}`] = value;
        } else elements[key] = { text: value };
      }
    return { theme: { fonts: { body: "Arial", heading: "Arial" } }, elements };
  }

  private async applyEdits(
    project: Project,
    destination: string,
    directory: string,
  ) {
    const edits = join(directory, "text-edits.json");
    await writeFile(edits, JSON.stringify(project.overrides));
    const chartScenes = join(directory, "chart-scenes.json");
    const scenes = await this.scenes(project.id);
    await writeFile(
      chartScenes,
      JSON.stringify(
        scenes
          .map((scene) => ({
            number: scene.number,
            elements: scene.elements.filter(
              (element) => element.target?.kind === "chartText",
            ),
          }))
          .filter((scene) => scene.elements.length),
      ),
    );
    await run(process.env.PYTHON || "python3", [
      "scripts/editor_scene.py",
      "--source",
      destination,
      "--mode",
      project.mode,
      "--output",
      destination,
      "--apply-edits",
      edits,
      "--chart-scenes",
      chartScenes,
    ]);
  }

  private async previewSource(id: string, revision: number) {
    const folder = this.store.path(id);
    const project = await this.store.read(id);
    if (revision === 0) return join(folder, "base.pptx");
    const destination = join(
      folder,
      "previews",
      `v5-${revision}`,
      "presentation.pptx",
    );
    const sceneFile = join(folder, "previews", `v5-${revision}`, "scenes.json");
    try {
      await access(sceneFile);
      return destination;
    } catch {}
    if (!Number.isInteger(revision) || revision !== project.revision)
      throw new EditorError(
        409,
        "The preview has changed. Reload the project.",
        "REVISION_CONFLICT",
      );
    const key = `${id}.${revision}`;
    let pending = this.previews.get(key);
    if (!pending) {
      pending = (async () => {
        const directory = join(folder, "previews", `v5-${revision}`);
        await mkdir(directory, { recursive: true });
        const config = join(directory, "config.json");
        await writeFile(config, JSON.stringify(await this.config(project)));
        if (project.mode === "fidelity")
          await copyFile(join(folder, "base.pptx"), destination);
        else
          await run(process.execPath, [
            "src/generate.mjs",
            "--mode",
            "responsive",
            "--config",
            config,
            "--output",
            destination,
          ]);
        if (project.mode === "responsive")
          await run(process.env.PYTHON || "python3", [
            "scripts/editor_scene.py",
            "--source",
            destination,
            "--output",
            destination,
            "--normalize-ids",
          ]);
        await this.applyEdits(project, destination, directory);
        await run(process.env.PYTHON || "python3", [
          "scripts/editor_scene.py",
          "--source",
          destination,
          "--mode",
          project.mode,
          "--output",
          sceneFile,
        ]);
        return destination;
      })();
      this.previews.set(key, pending);
    }
    try {
      return await pending;
    } finally {
      if (this.previews.get(key) === pending) this.previews.delete(key);
    }
  }

  async displayScene(id: string, number: number, revision: number) {
    const base = await this.scene(id, number);
    const project = await this.store.read(id);
    if (!Number.isInteger(revision) || project.revision !== revision)
      throw new EditorError(
        409,
        "The preview has changed. Reload the project.",
        "REVISION_CONFLICT",
      );
    const text = (element: SlideScene["elements"][number]) =>
      project.overrides[`${number}.${element.id}`] ?? element.originalText;
    if (revision === 0)
      return {
        ...base,
        elements: base.elements.map((e) => ({ ...e, text: text(e) })),
      };
    try {
      await this.previewSource(id, revision);
      const scenes: SlideScene[] = JSON.parse(
        await readFile(
          join(
            this.store.path(id),
            "previews",
            `v5-${revision}`,
            "scenes.json",
          ),
          "utf8",
        ),
      );
      const current = scenes.find((s) => s.number === number)!;
      return {
        ...current,
        chartTextError: base.chartTextError,
        elements: base.elements.map((element) => {
          let projected = current.elements.find((e) => e.id === element.id);
          if (
            !projected &&
            element.target?.kind === "chartText" &&
            element.target.chartBox
          ) {
            const frame = current.charts?.find(
              (chart) => chart.id === element.target?.ownerId,
            );
            if (frame) {
              const before = element.target.chartBox;
              const sx = frame.box.w / (before.w || 1),
                sy = frame.box.h / (before.h || 1);
              projected = {
                ...element,
                box: {
                  x: frame.box.x + (element.box.x - before.x) * sx,
                  y: frame.box.y + (element.box.y - before.y) * sy,
                  w: element.box.w * sx,
                  h: element.box.h * sy,
                },
                style: {
                  ...element.style,
                  fontSize: element.style.fontSize * Math.min(sx, sy),
                },
              };
            }
          }
          return {
            ...element,
            ...(projected
              ? {
                  box: projected.box,
                  style: projected.style,
                  paragraphs: projected.paragraphs,
                  transform: projected.transform,
                }
              : { paragraphs: text(element) === "" ? [] : element.paragraphs }),
            text: text(element),
          };
        }),
      };
    } catch (error) {
      if (error instanceof EditorError) throw error;
      return {
        ...base,
        elements: base.elements.map((e) => ({ ...e, text: text(e) })),
        layoutError:
          "Text saved, but the adaptive layout could not be recalculated. Shorten overflowing text before exporting.",
      };
    }
  }

  async background(id: string, number: number, revision: number) {
    const scene = await this.scene(id, number);
    const folder = this.store.path(id);
    const project = await this.store.read(id);
    const native = project.mode === "fidelity";
    const destination = join(
      folder,
      `background-v5-${scene.number}-${native ? 0 : revision}.png`,
    );
    try {
      await access(destination);
      return destination;
    } catch {}
    const key = `${id}.${number}.${native ? 0 : revision}`;
    let pending = this.backgrounds.get(key);
    if (!pending) {
      pending = (async () => {
        try {
          const source = native
            ? join(folder, "base.pptx")
            : await this.previewSource(id, revision);
          await run(process.env.PYTHON || "python3", [
            "scripts/editor_scene.py",
            "--source",
            source,
            "--mode",
            project.mode,
            "--background",
            String(number),
            "--output",
            destination,
            ...(scene.elements.some(
              (element) => element.target?.kind === "chartText",
            )
              ? [
                  "--chart-scenes",
                  join(folder, "chart-text-v5", `${number}.json`),
                ]
              : []),
          ]);
        } catch {
          throw new EditorError(
            503,
            "Full preview unavailable. Check LibreOffice and Poppler on the server.",
            "PREVIEW_UNAVAILABLE",
          );
        }
        return destination;
      })();
      this.backgrounds.set(key, pending);
    }
    try {
      return await pending;
    } finally {
      if (this.backgrounds.get(key) === pending) this.backgrounds.delete(key);
    }
  }

  async export(id: string): Promise<ExportJob> {
    // Freeze a revision before queuing. Subsequent edits cannot leak into this build.
    const project = await this.store.read(id);
    const job: ExportJob = {
      id: randomUUID(),
      projectId: id,
      revision: project.revision,
      status: "queued",
    };
    const folder = join(this.store.path(id), "exports", job.id);
    await mkdir(folder, { recursive: true });
    await writeFile(join(folder, "job.json"), JSON.stringify(job));
    await writeFile(
      join(folder, "config.json"),
      JSON.stringify(await this.config(project)),
    );
    this.activeJobs.add(job.id);
    this.queue = this.queue
      .catch(() => {})
      .then(async () => {
        job.status = "running";
        await writeFile(join(folder, "job.json"), JSON.stringify(job));
        try {
          await run(
            process.execPath,
            [
              join(repoRoot, "src/generate.mjs"),
              "--mode",
              project.mode,
              "--config",
              join(folder, "config.json"),
              "--output",
              join(folder, "presentation.pptx"),
            ],
            180_000,
          );
          if (project.mode === "responsive") {
            const output = join(folder, "presentation.pptx");
            await run(process.env.PYTHON || "python3", [
              "scripts/editor_scene.py",
              "--source",
              output,
              "--output",
              output,
              "--normalize-ids",
            ]);
          }
          await this.applyEdits(
            project,
            join(folder, "presentation.pptx"),
            folder,
          );
          job.status = "complete";
        } catch {
          job.status = "failed";
          job.error =
            "Could not generate the PPTX. Your edits are still saved; please try again.";
        } finally {
          await writeFile(join(folder, "job.json"), JSON.stringify(job));
          this.activeJobs.delete(job.id);
        }
      })
      .catch((error) => {
        this.activeJobs.delete(job.id);
        console.error("Export job failed", error);
      });
    return { ...job, status: "queued" };
  }

  jobFolder(id: string, jobId: string) {
    if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/.test(jobId))
      throw new EditorError(404, "Export not found.", "NOT_FOUND");
    return join(this.store.path(id), "exports", jobId);
  }

  async job(id: string, jobId: string): Promise<ExportJob> {
    await this.store.read(id);
    try {
      const job: ExportJob = JSON.parse(
        await readFile(join(this.jobFolder(id, jobId), "job.json"), "utf8"),
      );
      if (
        ["queued", "running"].includes(job.status) &&
        !this.activeJobs.has(jobId)
      ) {
        return {
          ...job,
          status: "failed",
          error: "The API restarted during export. Generate the file again.",
        };
      }
      return job;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT")
        throw new EditorError(404, "Export not found.", "NOT_FOUND");
      throw error;
    }
  }
}

export const editor = new EditorService();
