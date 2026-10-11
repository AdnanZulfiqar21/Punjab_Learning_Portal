// P18.S2.T3 (EXPOSURE-01): the browser bundle ships no source maps, credentials or server-only configuration names.
// Run after `next build`: node scripts/check-bundle.mjs [path to .next/static]
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(process.argv[2] ?? join(fileURLToPath(new URL(".", import.meta.url)), "..", ".next", "static"));
const RULES = [
  ["source map reference", /sourceMappingURL=/],
  ["private key", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["database URL with a password", /postgres(?:ql)?(?:\+\w+)?:\/\/[^\s"'`/]+:[^\s"'`@/]+@/],
  ["server configuration name", /\bPORTAL_[A-Z0-9_]{3,}/],
  ["cloud access key", /\bAKIA[0-9A-Z]{16}\b/],
  ["live payment key", /\b(?:sk|rk)_live_[0-9A-Za-z]{10,}/],
];

function* files(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* files(p);
    else yield p;
  }
}

const problems = [];
let count = 0;
for (const f of files(root)) {
  count += 1;
  if (f.endsWith(".map")) problems.push(`${f}: source map file`);
  if (!/\.(js|mjs|css|html|json|txt)$/.test(f)) continue;
  const text = readFileSync(f, "utf8");
  for (const [name, re] of RULES) if (re.test(text)) problems.push(`${f}: ${name}`);
}
if (count === 0) {
  console.error(`No files under ${root}; build first.`);
  process.exit(2);
}
if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log(`Checked ${count} client files: no source maps, credentials or server configuration names.`);
