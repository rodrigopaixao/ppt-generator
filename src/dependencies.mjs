import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import path from 'node:path';

const local = createRequire(import.meta.url);
// Normal npm dependencies first. Codex's bundled runtime is an optional offline fallback.
/**
 * Carrega pacote npm local; no Codex permite fallback offline explícito.
 * @param {string} name Nome do pacote (ex.: pptxgenjs ou sharp).
 * @returns {*} Exportação CommonJS do pacote.
 * local resolve a instalação do projeto; directory usa CODEX_NODE_MODULES ou
 * o runtime local. Só MODULE_NOT_FOUND aciona fallback; outros erros propagam.
 */
export function dependency(name) {
  try { return local(name); } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error;
    const directory = process.env.CODEX_NODE_MODULES || path.join(homedir(),
      '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
    return createRequire(path.join(directory, '_resolve.cjs'))(name);
  }
}
