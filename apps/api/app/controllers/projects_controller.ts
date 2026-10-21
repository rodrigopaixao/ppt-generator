import type { HttpContext } from "@adonisjs/core/http";
import { join } from "node:path";
import { editor } from "#services/editor_service";
import { EditorError } from "#services/errors";

export default class ProjectsController {
  async index() {
    return { projects: await editor.store.list() };
  }

  async create({ request, response }: HttpContext) {
    const document = await editor.create(
      request.input("name"),
      request.input("mode", "fidelity"),
    );
    return response.created(document);
  }

  async show({ params }: HttpContext) {
    return editor.document(params.id);
  }

  async slide({ params, request }: HttpContext) {
    const project = await editor.store.read(params.id);
    return editor.displayScene(
      params.id,
      Number(params.number),
      Number(request.input("revision", project.revision)),
    );
  }

  async update({ params, request }: HttpContext) {
    const scene = await editor.scene(params.id, Number(params.number));
    const project = await editor.store.edit(
      params.id,
      request.input("revision"),
      scene,
      request.input("elementId"),
      request.input("text"),
    );
    return { project };
  }

  async history({ params, request }: HttpContext) {
    const direction = request.input("direction");
    if (!["undo", "redo"].includes(direction))
      throw new EditorError(422, "Invalid action.", "INVALID_HISTORY");
    return {
      project: await editor.store.history(
        params.id,
        request.input("revision"),
        direction,
        await editor.scenes(params.id),
      ),
    };
  }

  async background({ params, request, response }: HttpContext) {
    const project = await editor.store.read(params.id);
    const path = await editor.background(
      params.id,
      Number(params.number),
      Number(request.input("revision", project.revision)),
    );
    response.header("Cache-Control", "private, max-age=31536000, immutable");
    return response.download(path);
  }

  async export({ params, response }: HttpContext) {
    return response.accepted(await editor.export(params.id));
  }
  async job({ params }: HttpContext) {
    return editor.job(params.id, params.jobId);
  }
  async download({ params, response }: HttpContext) {
    const job = await editor.job(params.id, params.jobId);
    if (job.status !== "complete")
      throw new EditorError(409, "Export is not ready yet.", "EXPORT_PENDING");
    return response.attachment(
      join(editor.jobFolder(params.id, params.jobId), "presentation.pptx"),
      `slides-r${job.revision}.pptx`,
    );
  }
}
