// INLINE-MATH-01 (MATHS-11-01, owner 2026-11-05): mathematics written inside lesson text, between \( and \) (in the
// line) or \[ and \] (on a line of its own). The web typesets it with KaTeX (apps/web/src/lib/inline-math.ts); the
// apps have no equation renderer yet (§5.4), so here each formula is shown as readable plain text: fractions as a/b,
// roots with √, powers as superscripts where Unicode has them, Greek letters and operators as symbols. Text without
// these delimiters is untouched, so every other book reads exactly as before.

const SUP: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
  "+": "⁺", "-": "⁻", "−": "⁻", "=": "⁼", "(": "⁽", ")": "⁾", n: "ⁿ", i: "ⁱ",
};
const SUB: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
  "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎", n: "ₙ",
};
const SYMBOLS: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", Delta: "Δ", epsilon: "ε", theta: "θ", lambda: "λ", mu: "μ", pi: "π",
  rho: "ρ", sigma: "σ", Sigma: "Σ", tau: "τ", phi: "φ", varphi: "φ", omega: "ω", Omega: "Ω",
  cdot: "·", times: "×", div: "÷", pm: "±", mp: "∓", le: "≤", leq: "≤", ge: "≥", geq: "≥", ne: "≠", neq: "≠",
  approx: "≈", equiv: "≡", infty: "∞", in: "∈", notin: "∉", subset: "⊂", cup: "∪", cap: "∩", forall: "∀",
  exists: "∃", Rightarrow: "⇒", implies: "⇒", Leftrightarrow: "⇔", iff: "⇔", rightarrow: "→", to: "→",
  leftarrow: "←", therefore: "∴", because: "∵", circ: "°", angle: "∠", ldots: "…", cdots: "⋯", dots: "…",
  wedge: "∧", vee: "∨", neg: "¬", prime: "′", degree: "°",
};
const FUNCS = ["sin", "cos", "tan", "cot", "sec", "csc", "cosec", "log", "ln", "arg", "lim", "exp", "max", "min"];

/** The argument of a command: a {group} (returned without braces) or one character. */
function arg(s: string, at: number): [string, number] {
  while (s[at] === " ") at++;
  if (s[at] !== "{") return [s[at] ?? "", at + 1];
  let depth = 0;
  for (let k = at; k < s.length; k++) {
    if (s[k] === "{") depth++;
    else if (s[k] === "}" && --depth === 0) return [s.slice(at + 1, k), k + 1];
  }
  return [s.slice(at + 1), s.length];
}

const simple = (t: string) => /^[\w.′]+$/u.test(t) || /^[\d.]+$/.test(t);
const wrap = (t: string) => (simple(t) ? t : `(${t})`);
const script = (t: string, map: Record<string, string>, mark: string) =>
  [...t].every((ch) => map[ch]) ? [...t].map((ch) => map[ch]).join("") : `${mark}${wrap(t)}`;

/** One LaTeX formula as readable plain text. */
export function latexToText(latex: string): string {
  const s = latex;
  let out = "";
  let k = 0;
  while (k < s.length) {
    const ch = s[k];
    if (ch === "\\") {
      const m = /^\\([A-Za-z]+|.)/.exec(s.slice(k));
      const name = m ? m[1] : "";
      k += 1 + name.length;
      if (/^[A-Za-z]/.test(name) && s[k] === " ") k++; // the space that ends a command name is not text
      if (name === "frac" || name === "dfrac" || name === "tfrac") {
        const [a, k1] = arg(s, k);
        const [b, k2] = arg(s, k1);
        out += `${wrap(latexToText(a))}/${wrap(latexToText(b))}`;
        k = k2;
      } else if (name === "sqrt") {
        let index = "";
        if (s[k] === "[") {
          const e = s.indexOf("]", k);
          index = s.slice(k + 1, e);
          k = e + 1;
        }
        const [a, k1] = arg(s, k);
        out += `${index ? script(index, SUP, "") : ""}√${wrap(latexToText(a))}`;
        k = k1;
      } else if (name === "overline" || name === "bar") {
        const [a, k1] = arg(s, k);
        const t = latexToText(a);
        out += t.length === 1 ? `${t}̅` : `conj(${t})`;
        k = k1;
      } else if (["text", "mathrm", "operatorname", "mathbf", "mathit", "textbf", "boldsymbol"].includes(name)) {
        const [a, k1] = arg(s, k);
        out += name === "text" ? a : latexToText(a);
        k = k1;
      } else if (name === "mathbb") {
        const [a, k1] = arg(s, k);
        out += ({ R: "ℝ", C: "ℂ", N: "ℕ", Z: "ℤ", Q: "ℚ" } as Record<string, string>)[a] ?? a;
        k = k1;
      } else if (name === "left" || name === "right" || name === "big" || name === "Big" || name === "bigg") {
        // the delimiter that follows is kept as written
      } else if (name === "," || name === ";" || name === ":" || name === "quad" || name === "qquad" || name === " ") {
        out += name === "qquad" ? "    " : name === "quad" ? "  " : " ";
      } else if (name === "!") {
        // negative thin space
      } else if (name === "\\") {
        out += "\n";
      } else if (name === "{" || name === "}" || name === "%" || name === "&" || name === "_" || name === "#") {
        out += name;
      } else if (name === "begin" || name === "end") {
        k = arg(s, k)[1];
      } else if (FUNCS.includes(name)) {
        out += `${name} `;
      } else if (SYMBOLS[name] !== undefined) {
        out += SYMBOLS[name];
      } else {
        out += name; // an unknown command: its name, never an empty gap
      }
    } else if (ch === "^" || ch === "_") {
      const [a, k1] = arg(s, k + 1);
      const t = latexToText(a);
      out += ch === "^" ? script(t, SUP, "^") : script(t, SUB, "_");
      k = k1;
    } else if (ch === "{" || ch === "}") {
      k++;
    } else if (ch === "&") {
      k++;
    } else if (ch === "~") {
      out += " ";
      k++;
    } else {
      out += ch;
      k++;
    }
  }
  return out.replace(/[ \t]{2,}/g, " ").replace(/ ([,.;)])/g, "$1").trim();
}

const MATH = /\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]/g;

/** Whether a text carries any formula. */
export function hasMath(text: string): boolean {
  return text.includes("\\(") || text.includes("\\[");
}

/** Lesson text with every formula as readable plain text (a \[ … \] formula on its own line). */
export function plainMath(text: string): string {
  if (!hasMath(text)) return text;
  // A line of its own takes the line breaks written around it, so it adds no blank lines.
  return text
    .replace(/[ \t]*\n?\\\[([\s\S]+?)\\\]\n?/g, (_all, display: string) => `\n${latexToText(display)}\n`)
    .replace(MATH, (_all, inline: string | undefined) => latexToText(inline ?? ""))
    .replace(/^\n+|\n+$/g, "");
}

/** Every text of a block list with its formulas as plain text (the formula blocks' own LaTeX and asset ids kept). */
export function plainBlocks<T>(value: T): T {
  if (typeof value === "string") return plainMath(value) as T;
  if (Array.isArray(value)) return value.map(plainBlocks) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = k === "latex" ? v : plainBlocks(v);
    return out as T;
  }
  return value;
}
