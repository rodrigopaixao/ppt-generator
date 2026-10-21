import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { repoRoot } from "./paths.js";

const exec = promisify(execFile);
// The generator runs outside Adonis's event loop; no user-controlled commands or paths.
export async function run(command: string, args: string[], timeout = 120_000) {
  return exec(command, args, {
    cwd: repoRoot,
    timeout,
    maxBuffer: 8 * 1024 * 1024,
  });
}
