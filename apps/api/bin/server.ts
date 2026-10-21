import "reflect-metadata";
import { Ignitor, prettyPrintError } from "@adonisjs/core";

process.env.HOST ||= "127.0.0.1";
process.env.PORT ||= "3333";
const APP_ROOT = new URL("../", import.meta.url);
new Ignitor(APP_ROOT, {
  importer: (filePath) =>
    import(
      filePath.startsWith(".") ? new URL(filePath, APP_ROOT).href : filePath
    ),
})
  .tap((app) => {
    app.listen("SIGTERM", () => app.terminate());
    app.listen("SIGINT", () => app.terminate());
  })
  .httpServer()
  .start()
  .catch((error) => {
    process.exitCode = 1;
    prettyPrintError(error);
  });
