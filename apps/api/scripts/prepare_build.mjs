import { copyFile } from "node:fs/promises";

// Keep Node's #imports relative to the compiled application in production.
await copyFile(
  new URL("../package.json", import.meta.url),
  new URL("../build/package.json", import.meta.url),
);
