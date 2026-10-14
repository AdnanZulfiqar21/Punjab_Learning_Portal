// Every request the mobile app makes (src/lib/api.ts) names a path and method the API publishes
// (packages/contracts/openapi.json). Found on 2026-10-14: the page controls (MOBILE-TRANSFORMS-01) sent POST to a PUT
// route, so every turn or contrast change would have been refused. A host-side check of the source; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { it } from "node:test";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "../src/lib/api.ts"), "utf8");
const contract = JSON.parse(readFileSync(join(here, "../../../packages/contracts/openapi.json"), "utf8")) as {
  paths: Record<string, Record<string, unknown>>;
};

/** The text of one call's arguments, from the opening "(" to its matching ")", skipping strings and templates. */
function callArgs(text: string, open: number): string {
  let depth = 0;
  let i = open;
  const templates: number[] = []; // brace depth at which each open template's ${ } began
  let quote: string | null = null;
  for (; i < text.length; i++) {
    const ch = text[i];
    if (quote) {
      if (ch === "\\") i++;
      else if (ch === quote) quote = null;
      continue;
    }
    if (templates.length && depth === templates[templates.length - 1] && ch === "`") {
      templates.pop();
      continue;
    }
    if (ch === '"' || ch === "'") quote = ch;
    else if (ch === "`") {
      // a template: scan to its end, entering ${ } as code
      let j = i + 1;
      for (; j < text.length; j++) {
        if (text[j] === "\\") j++;
        else if (text[j] === "`") break;
        else if (text[j] === "$" && text[j + 1] === "{") {
          templates.push(depth);
          depth += 1;
          i = j + 1;
          break;
        }
      }
      if (j < text.length && text[j] === "`" && (templates.length === 0 || i < j)) i = j;
    } else if (ch === "(" || ch === "{" || ch === "[") depth += 1;
    else if (ch === ")" || ch === "}" || ch === "]") {
      depth -= 1;
      if (depth === 0 && ch === ")") return text.slice(open + 1, i);
    }
  }
  throw new Error(`unbalanced call at ${open}`);
}

/** "/v1/a/${x}/b?y=${z}" -> "/v1/a/{}/b" (query strings and conditional suffixes dropped). */
function pathOf(firstArg: string): string | null {
  const m = /^\s*[`"']([^`"']*)/.exec(firstArg);
  if (!m) return null;
  let raw = firstArg.trim().slice(1);
  raw = raw.replace(/\$\{(?:[^{}]|\{[^{}]*\})*\}/g, (inner) => (/[?`]/.test(inner) ? "" : "{}"));
  const end = raw.search(/[`"'?]/);
  return end === -1 ? raw : raw.slice(0, end);
}

function calls(): { path: string; methods: string[]; at: number }[] {
  const out: { path: string; methods: string[]; at: number }[] = [];
  const re = /\b(request|getJSON)<[^>(]*(?:<[^>]*>[^>(]*)*>\(/g;
  for (let m = re.exec(source); m; m = re.exec(source)) {
    const args = callArgs(source, m.index + m[0].length - 1);
    const path = pathOf(args);
    if (!path) continue;
    const methodText = /method:\s*([^,}\n]+)/.exec(args)?.[1] ?? '"GET"';
    const methods = [...methodText.matchAll(/"([A-Z]+)"/g)].map((x) => x[1]);
    out.push({ path, methods: methods.length ? methods : ["GET"], at: source.slice(0, m.index).split("\n").length });
  }
  return out;
}

// The development sign-in adapter: served only in development and tests, refused elsewhere, and so deliberately left
// out of the published contract.
const DEVELOPMENT_ONLY = new Set(["/v1/dev-auth/register", "/v1/dev-auth/token"]);

const published = new Map<string, Set<string>>(
  Object.entries(contract.paths).map(([p, ops]) => [p.replace(/\{[^}]+\}/g, "{}"), new Set(Object.keys(ops).map((k) => k.toUpperCase()))]),
);

it("finds the app's requests (the parser still understands api.ts)", () => {
  assert.ok(calls().length >= 60, `only ${calls().length} requests found`);
});

it("every mobile request uses a path and method the API publishes", () => {
  const wrong = calls().flatMap(({ path, methods, at }) => {
    if (DEVELOPMENT_ONLY.has(path)) return [];
    const ops = published.get(path);
    if (!ops) return [`api.ts:${at} ${path}: no such path`];
    return methods.filter((m) => !ops.has(m)).map((m) => `api.ts:${at} ${m} ${path}: the API has ${[...ops].join(", ")}`);
  });
  assert.deepEqual(wrong, []);
});
