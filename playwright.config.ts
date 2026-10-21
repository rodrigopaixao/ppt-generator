import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  timeout: 150_000,
  expect: { timeout: 15_000 },
  use: {
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    baseURL: "http://127.0.0.1:3100",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "npm run dev -w @pptx/api",
      url: "http://127.0.0.1:3344/api/health",
      env: { PORT: "3344", EDITOR_DATA_DIR: path.resolve("output/editor-e2e") },
      timeout: 30_000,
    },
    {
      command: "npm run dev -w @pptx/web -- --port 3100",
      url: "http://127.0.0.1:3100",
      env: { API_URL: "http://127.0.0.1:3344", NEXT_DIST_DIR: ".next-e2e" },
      timeout: 60_000,
    },
  ],
});
