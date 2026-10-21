import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import path from 'node:path';

const local = createRequire(import.meta.url);
// Normal npm dependencies first. Codex's bundled runtime is an optional offline fallback.
/**
 * Load a local npm package, with an explicit offline fallback in Codex. name is the package
 * name, such as pptxgenjs or sharp. Return its CommonJS exports. local resolves the project
 * installation; directory uses CODEX_NODE_MODULES or the local runtime. Only
 * MODULE_NOT_FOUND triggers fallback; other errors propagate.
 *
 * @param {string} name
 * @returns {*}
 */
export function dependency(name) {
  try { return local(name); } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error;
    const directory = process.env.CODEX_NODE_MODULES || path.join(homedir(),
      '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
    return createRequire(path.join(directory, '_resolve.cjs'))(name);
  }
}
