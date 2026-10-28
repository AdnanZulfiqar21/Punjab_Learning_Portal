// CODE-RUNNER-01: the Python runtime (Pyodide) is served from this site's own origin, so the page's CSP needs no outside
// script or connect source. Its files come from the pinned `pyodide` package and are copied into public/pyodide/
// before `next dev` / `next build`; the copy is not committed (.gitignore).
import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const FILES = ["pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"];

const require = createRequire(import.meta.url);
const from = dirname(require.resolve("pyodide/package.json"));
const to = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "pyodide");
mkdirSync(to, { recursive: true });
for (const name of FILES) {
  const src = join(from, name);
  const dest = join(to, name);
  if (existsSync(dest) && statSync(dest).size === statSync(src).size && statSync(dest).mtimeMs >= statSync(src).mtimeMs) continue;
  copyFileSync(src, dest);
}
console.log(`pyodide: ${FILES.length} files in public/pyodide`);
