import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

function findRoot() {
  let current = dirname(fileURLToPath(import.meta.url));
  while (dirname(current) !== current) {
    const manifest = join(current, "package.json");
    if (
      existsSync(manifest) &&
      JSON.parse(readFileSync(manifest, "utf8")).name ===
        "context-slide-components"
    )
      return current;
    current = dirname(current);
  }
  throw new Error("Set REPO_ROOT to the generator repository");
}
export const repoRoot = process.env.REPO_ROOT
  ? resolve(process.env.REPO_ROOT)
  : findRoot();
export const dataRoot = process.env.EDITOR_DATA_DIR
  ? resolve(process.env.EDITOR_DATA_DIR)
  : join(repoRoot, ".editor-data");
export const sourcePath = join(
  repoRoot,
  "2606 Context Enriched Slide Repository.pptx",
);
