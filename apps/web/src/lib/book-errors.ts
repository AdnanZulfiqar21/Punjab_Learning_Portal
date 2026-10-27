// BOOK-CORRECTION-01: the English lesson keeps the textbook's printed wording, errors included. A block's `book_errors`
// names the printed passages that are wrong; the reader marks them in red and a `correction` callout after the block
// gives the right version. Identical in apps/web and apps/mobile (a host test compares the two files).

export type Piece = { text: string; error: boolean };

export function bookErrors(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((m): m is string => typeof m === "string" && m.length > 0) : [];
}

// A printed equation is shown once, its wrong part in red inside the typeset formula. The marks that occur in the LaTeX
// are coloured with a sentinel colour (KaTeX runs untrusted, so no classes); the typeset HTML's sentinel is then
// swapped for the theme's danger colours, so the red follows light and dark mode.
const SENTINEL = "#a31d1e";

/** The LaTeX with each mark that occurs in it wrapped in the sentinel colour. */
export function markLatex(latex: string, marks: string[]): string {
  const inLatex = marks.filter((m) => latex.includes(m)).sort((a, b) => b.length - a.length);
  if (!inLatex.length) return latex;
  let out = "";
  let i = 0;
  while (i < latex.length) {
    const hit = inLatex.find((m) => latex.startsWith(m, i));
    if (hit) {
      out += `\\textcolor{${SENTINEL}}{${hit}}`;
      i += hit.length;
    } else {
      out += latex[i];
      i += 1;
    }
  }
  return out;
}

/** Typeset HTML with the sentinel colour replaced by the theme's book-error colours. */
export function paintBookErrors(html: string): string {
  return html.replaceAll(`color:${SENTINEL};`, "color:var(--danger);background-color:var(--danger-soft);");
}

/** Splits text into plain and marked pieces. Every occurrence of a mark is marked; where marks overlap, the one that
 * starts first wins, and of two starting together the longer. */
export function markPieces(text: string, marks: string[]): Piece[] {
  if (!marks.length || !text) return [{ text, error: false }];
  const pieces: Piece[] = [];
  let plain = "";
  let i = 0;
  while (i < text.length) {
    let hit = "";
    for (const m of marks) if (m.length > hit.length && text.startsWith(m, i)) hit = m;
    if (hit) {
      if (plain) pieces.push({ text: plain, error: false });
      pieces.push({ text: hit, error: true });
      plain = "";
      i += hit.length;
    } else {
      plain += text[i];
      i += 1;
    }
  }
  if (plain) pieces.push({ text: plain, error: false });
  return pieces;
}
