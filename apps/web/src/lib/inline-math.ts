// INLINE-MATH-01 (MATHS-11-01, owner 2026-11-05): mathematics written inside a sentence. Lesson text stays plain text;
// a formula inside it is LaTeX between \( and \) (in the line) or \[ and \] (on a line of its own), as authored in the
// Mathematics lessons. Text without these delimiters is untouched, so every other book reads exactly as before.
// Same rules as the app (apps/mobile/src/lib/inline-math.ts).

export type MathPiece = { kind: "text"; text: string } | { kind: "math"; latex: string; display: boolean };

const MATH = /\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]/g;

/** Whether a text carries any formula. */
export function hasMath(text: string): boolean {
  return text.includes("\\(") || text.includes("\\[");
}

/** The text split into plain runs and formulas, in order. An unclosed delimiter stays plain text. */
export function mathPieces(text: string): MathPiece[] {
  const out: MathPiece[] = [];
  let at = 0;
  for (const m of text.matchAll(MATH)) {
    if (m.index > at) out.push({ kind: "text", text: text.slice(at, m.index) });
    out.push(m[1] !== undefined ? { kind: "math", latex: m[1], display: false } : { kind: "math", latex: m[2], display: true });
    at = m.index + m[0].length;
  }
  if (at < text.length) out.push({ kind: "text", text: text.slice(at) });
  return out;
}
