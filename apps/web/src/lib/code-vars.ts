// CODE-RUNNER-01: a printed Python program can be run in the Roman Urdu tab, and a student may change only the values
// of its variables (owner, 2026-10-28: "students variables ke value change kr ka out dakh saky sirf variable ke
// value"). This finds the top-level lines `name = <plain value>` and `name = Something(<plain values>)` and puts new
// values in; the rest of the program stays as printed. Identical in apps/web and apps/mobile (a host test compares the
// two files).

/** A value a student can change: on line `line` (0-based) the value at [start, end). `key` tells values apart (two may
 * share a line); `label` names it for the student: the variable (`x`), or the call it is given to (`object1 → Student`,
 * `car → Car color`). */
export type EditableVar = { key: string; line: number; name: string; label: string; value: string; start: number; end: number };

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

/** The values a student may change, in program order: `name = <plain value>`, and the plain arguments of
 * `name = Something(<plain values>)` (owner, 2026-10-29, on `object1 = Student("Ali")`: let students change "Ali").
 * Lines inside a block (indented) are left alone. */
export function editableVars(code: string): EditableVar[] {
  const out: EditableVar[] = [];
  code.split(/\r?\n/).forEach((text, line) => {
    const m = /^([A-Za-z_]\w*)(\s*=\s*)(.*)$/.exec(text);
    if (!m) return;
    const name = m[1];
    const start = m[1].length + m[2].length;
    const end = start + text.slice(start, codeEnd(text, start)).trimEnd().length;
    const value = text.slice(start, end);
    if (isPlainValue(value)) {
      out.push({ key: `${line}:${start}`, line, name, label: name, value, start, end });
      return;
    }
    // A call whose arguments include plain values: each such argument gets its own box.
    const call = /^([A-Za-z_][\w.]*)\s*\(/.exec(value);
    if (!call || value[value.length - 1] !== ")") return;
    const args = splitArgs(text, start + call[0].length, end - 1);
    if (!args) return;
    args.forEach((a, n) => {
      const kw = /^([A-Za-z_]\w*)\s*=(?!=)\s*/.exec(text.slice(a.start, a.end));
      const from = a.start + (kw ? kw[0].length : 0);
      const v = text.slice(from, a.end);
      if (!isPlainValue(v)) return;
      const which = kw ? ` ${kw[1]}` : args.length > 1 ? ` (${n + 1})` : "";
      out.push({ key: `${line}:${from}`, line, name, label: `${name} → ${call[1]}${which}`, value: v, start: from, end: a.end });
    });
  });
  return out;
}

/** Where the code of a line ends: before a trailing comment; a `#` inside a string is code. */
function codeEnd(text: string, from: number): number {
  for (let i = from, q = ""; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === "\\") i++;
      else if (ch === q) q = "";
    } else if (ch === '"' || ch === "'") q = ch;
    else if (ch === "#") return i;
  }
  return text.length;
}

/** The arguments between `from` and the call's closing bracket at `to`, as trimmed [start, end) spans; null if the
 * brackets don't balance. */
function splitArgs(text: string, from: number, to: number): { start: number; end: number }[] | null {
  const spans: { start: number; end: number }[] = [];
  const push = (a: number, b: number) => {
    while (a < b && text[a] === " ") a++;
    while (b > a && text[b - 1] === " ") b--;
    if (b > a) spans.push({ start: a, end: b });
  };
  let depth = 0;
  let begin = from;
  for (let i = from, q = ""; i < to; i++) {
    const ch = text[i];
    if (q) {
      if (ch === "\\") i++;
      else if (ch === q) q = "";
    } else if (ch === '"' || ch === "'") q = ch;
    else if ("([{".includes(ch)) depth++;
    else if (")]}".includes(ch)) {
      if (--depth < 0) return null;
    } else if (ch === "," && depth === 0) {
      push(begin, i);
      begin = i + 1;
    }
  }
  if (depth !== 0) return null;
  push(begin, to);
  return spans;
}

/** The program with the given values (by `key`) put in; a value that is not plain keeps the printed one. */
export function withValues(code: string, vars: EditableVar[], values: Record<string, string>): string {
  const lines = code.split(/\r?\n/);
  // Right to left within a line, so earlier positions stay valid.
  for (const v of [...vars].sort((a, b) => a.line - b.line || b.start - a.start)) {
    const next = values[v.key];
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
