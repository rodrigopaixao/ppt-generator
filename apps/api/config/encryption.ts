import { defineConfig, drivers } from "@adonisjs/core/encryption";
import { appKey } from "./app.js";

export default defineConfig({
  default: "app",
  list: { app: drivers.aes256gcm({ id: "app", keys: [appKey] }) },
});
