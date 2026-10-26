// BOOK-CORRECTION-01: the English lesson keeps the textbook's printed wording, errors included. A block's `book_errors`
// names the printed passages that are wrong; the reader marks them in red and a `correction` callout after the block
// gives the right version. Identical in apps/web and apps/mobile (a host test compares the two files).

export type Piece = { text: string; error: boolean };

export function bookErrors(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((m): m is string => typeof m === "string" && m.length > 0) : [];
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
