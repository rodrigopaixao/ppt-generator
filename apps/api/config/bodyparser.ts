import { defineConfig } from "@adonisjs/core/bodyparser";

export default defineConfig({
  allowedMethods: ["POST", "PUT", "PATCH", "DELETE"],
  json: { types: ["application/json"], limit: "128kb" },
});
