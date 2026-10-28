// CODE-RUNNER-01: a printed Python program can be run in the Roman Urdu tab, and a student may change only the values
// of its variables (owner, 2026-10-28: "students variables ke value change kr ka out dakh saky sirf variable ke
// value"). This finds the lines `name = <plain value>` at the program's top level and puts new values in; the rest of
// the program stays as printed. Identical in apps/web and apps/mobile (a host test compares the two files).

/** A value a student can change: line `line` (0-based) holds `name = value`, the value at [start, end) of that line. */
export type EditableVar = { line: number; name: string; value: string; start: number; end: number };

// A plain value: numbers, strings, True/False/None and lists, tuples or dicts of them, on one line.
const TOKEN = /\s+|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|True\b|False\b|None\b|[[\](){},:]/y;
const PAIRS: Record<string, string> = { "]": "[", ")": "(", "}": "{" };

/** True for a plain value (no names, calls or operators), so a changed value can never change the program itself. */
export function isPlainValue(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  const open: string[] = [];
  let tokens = 0;
  TOKEN.lastIndex = 0;
  while (TOKEN.lastIndex < t.length) {
    const at = TOKEN.lastIndex;
    const m = TOKEN.exec(t);
    if (!m || m.index !== at) return false;
    const tok = m[0];
    if (/^\s+$/.test(tok)) continue;
    tokens += 1;
    if ("[({".includes(tok)) open.push(tok);
    else if (tok in PAIRS && open.pop() !== PAIRS[tok]) return false;
    else if ((tok === "," || tok === ":") && !open.length) return false;
  }
  return open.length === 0 && (tokens === 1 || "[({".includes(t[0]));
}

/** The values a student may change, in program order. Lines inside a block (indented) are left alone. */
export function editableVars(code: string): EditableVar[] {
  const out: EditableVar[] = [];
  code.split("\n").forEach((text, line) => {
    const m = /^([A-Za-z_]\w*)(\s*=\s*)(.*)$/.exec(text);
    if (!m) return;
    const start = m[1].length + m[2].length;
    // The value runs to a trailing comment, if any; a `#` inside a string is part of the value.
    let end = text.length;
    for (let i = start, q = ""; i < text.length; i++) {
      const ch = text[i];
      if (q) {
        if (ch === "\\") i++;
        else if (ch === q) q = "";
      } else if (ch === '"' || ch === "'") q = ch;
      else if (ch === "#") {
        end = i;
        break;
      }
    }
    const raw = text.slice(start, end);
    const value = raw.trimEnd();
    if (!isPlainValue(value)) return;
    out.push({ line, name: m[1], value, start, end: start + value.length });
  });
  return out;
}

/** The program with the given values (by line) put in; a value that is not plain keeps the printed one. */
export function withValues(code: string, vars: EditableVar[], values: Record<number, string>): string {
  const lines = code.split("\n");
  for (const v of vars) {
    const next = values[v.line];
    if (next === undefined || !isPlainValue(next)) continue;
    const text = lines[v.line];
    lines[v.line] = text.slice(0, v.start) + next.trim() + text.slice(v.end);
  }
  return lines.join("\n");
}

/** The prompts of the program's `input(...)` calls, in order ("" where the prompt is not a plain string). */
export function inputPrompts(code: string): string[] {
  const out: string[] = [];
  for (const m of code.matchAll(/\binput\s*\(\s*("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')?/g)) out.push(m[1] ? m[1].slice(1, -1) : "");
  return out;
}
