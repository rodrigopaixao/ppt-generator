import { ExceptionHandler, type HttpContext } from "@adonisjs/core/http";
import { EditorError } from "#services/errors";

export default class Handler extends ExceptionHandler {
  async handle(error: unknown, ctx: HttpContext) {
    if (error instanceof EditorError) {
      return ctx.response
        .status(error.status)
        .send({ error: error.message, code: error.code });
    }
    const status = Number((error as { status?: number })?.status);
    if (status >= 400 && status < 500) {
      return ctx.response
        .status(status)
        .send({ error: "Invalid request.", code: "INVALID_REQUEST" });
    }
    ctx.logger.error({ err: error }, "Editor request failed");
    return ctx.response.internalServerError({
      error: "Could not complete the operation. Please try again.",
      code: "INTERNAL_ERROR",
    });
  }
}
