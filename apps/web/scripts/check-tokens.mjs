// P02.S2.T1 (TOKENS-01): the web and the app share one colour token table in value. The web's CSS custom properties
// (apps/web/src/app/globals.css) and the app's palette (apps/mobile/src/constants/theme.ts) are written separately, so
// this check fails CI when a colour in one no longer matches the other, in either theme. Run from the repository root.
import { readFileSync } from "node:fs";

const css = readFileSync("apps/web/src/app/globals.css", "utf8");
const ts = readFileSync("apps/mobile/src/constants/theme.ts", "utf8");

// web custom property -> app palette key
const PAIRS = {
  background: "background",
  surface: "surface",
  "surface-muted": "surfaceMuted",
  foreground: "text",
  muted: "muted",
  border: "border",
  accent: "accent",
  "accent-soft": "accentSoft",
  warn: "warn",
  "warn-soft": "warnSoft",
  danger: "danger",
  "danger-soft": "dangerSoft",
};

function cssBlock(selector) {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`globals.css has no ${selector} block`);
  const open = css.indexOf("{", start);
  return css.slice(open + 1, css.indexOf("}", open));
}

function tsBlock(theme) {
  const start = ts.indexOf(`${theme}: {`);
  if (start < 0) throw new Error(`theme.ts has no ${theme} palette`);
  return ts.slice(start, ts.indexOf("}", start));
}

function values(block, pattern) {
  const out = {};
  for (const m of block.matchAll(pattern)) out[m[1]] = m[2].toLowerCase();
  return out;
}

const HEX = /--([a-z-]+):\s*(#[0-9a-fA-F]{6})/g;
const web = {
  light: values(cssBlock(":root {"), HEX),
  dark: values(cssBlock(':root[data-theme="dark"] {'), HEX),
};
// The system dark theme and a device's chosen dark theme are written twice in globals.css: they must agree too.
const systemDark = values(cssBlock(':root:not([data-theme="light"]) {'), HEX);
const app = {
  light: values(tsBlock("light"), /(\w+):\s*"(#[0-9a-fA-F]{6})"/g),
  dark: values(tsBlock("dark"), /(\w+):\s*"(#[0-9a-fA-F]{6})"/g),
};

const problems = [];
for (const theme of ["light", "dark"]) {
  for (const [cssName, appName] of Object.entries(PAIRS)) {
    const a = web[theme][cssName];
    const b = app[theme][appName];
    if (!a || !b) problems.push(`${theme}: ${cssName}/${appName} is missing (web ${a ?? "none"}, app ${b ?? "none"})`);
    else if (a !== b) problems.push(`${theme}: --${cssName} is ${a} on the web but ${appName} is ${b} in the app`);
  }
}
for (const [name, value] of Object.entries(web.dark)) {
  if (systemDark[name] !== value) problems.push(`dark: --${name} is ${systemDark[name] ?? "missing"} for the system theme but ${value} when chosen`);
}
if (problems.length) {
  console.error("Design tokens differ between web and app:\n" + problems.map((p) => `  - ${p}`).join("\n"));
  process.exit(1);
}
console.log(`Design tokens match: ${Object.keys(PAIRS).length} colours in both themes.`);
