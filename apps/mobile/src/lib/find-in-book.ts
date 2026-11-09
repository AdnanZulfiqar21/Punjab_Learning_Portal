// MCQ-BOOK-LINK-01 (owner, 2026-11-08): a practice MCQ's "See in book" opens its Learn topic with the book's words, and
// the page marks them like a highlighter and scrolls to them. Pure rules for host tests; the web finds the same words in
// its page (apps/web/src/components/find-in-book.tsx).

/** Whitespace squashed to single spaces, with where each kept character came from in the original text. */
function squashed(text: string): { s: string; at: number[] } {
  let s = "";
  const at: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const ch = /\s/.test(text[i]) ? " " : text[i];
    if (ch === " " && (s === "" || s.endsWith(" "))) continue;
    s += ch;
    at.push(i);
  }
  return { s, at };
}

const MIN_PIECE = 15; // a shorter overlap at a piece's edge could be chance

/**
 * The part of `text` to mark for `quote`, as [start, end) in `text`: the whole quote when the text holds it; when a
 * paragraph is drawn in two pieces (beside a side figure, then below it), the quote's part in this piece.
 */
export function findRange(text: string, quote: string): [number, number] | null {
  const q = squashed(quote).s.trim();
  if (!q || !text) return null;
  const { s, at } = squashed(text);
  const span = (from: number, to: number): [number, number] => [at[from], at[to - 1] + 1];
  const full = s.indexOf(q);
  if (full >= 0) return span(full, full + q.length);
  const t = s.trim();
  const lead = s.indexOf(t);
  if (t.length >= MIN_PIECE && q.includes(t)) return span(lead, lead + t.length); // the whole piece is quoted
  // The quote starts in this piece and goes on in the next.
  for (let n = Math.min(q.length - 1, t.length); n >= MIN_PIECE; n--) {
    if (t.endsWith(q.slice(0, n))) return span(lead + t.length - n, lead + t.length);
  }
  // The quote began in the piece before and ends here.
  for (let n = Math.min(q.length - 1, t.length); n >= MIN_PIECE; n--) {
    if (t.startsWith(q.slice(q.length - n))) return span(lead, lead + n);
  }
  return null;
}

/** Every string inside a block (its text, items, cells, steps…), for finding which block holds the quote. */
function strings(v: unknown, out: string[]): string[] {
  if (typeof v === "string") out.push(v);
  else if (Array.isArray(v)) v.forEach((x) => strings(x, out));
  else if (v && typeof v === "object") Object.values(v).forEach((x) => strings(x, out));
  return out;
}

/** The index of the first block whose text holds the quote, or -1. */
export function findBlock(blocks: readonly unknown[], quote: string): number {
  const q = squashed(quote).s.trim();
  if (!q) return -1;
  return blocks.findIndex((b) => strings(b, []).some((x) => squashed(x).s.includes(q)));
}
