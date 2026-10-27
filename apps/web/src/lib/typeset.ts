import "server-only";
import katex from "katex";
import "katex/contrib/mhchem";
import "katex/dist/katex-swap.min.css";
import { bookErrors, markLatex, paintBookErrors } from "@/lib/book-errors";
import { KATEX_OPTIONS } from "@/lib/katex-options";

/** P01.S4.T2: typeset a block list's equations on the server, so server-rendered pages ship no KaTeX JavaScript (only
 * its CSS, and the fonts a formula uses). Keyed by block index; `null` marks a formula that can't be typeset, so the
 * browser shows its reviewed rendering at once instead of downloading KaTeX to fail again. */
export function typesetEquations(blocks: readonly { type: string; [key: string]: unknown }[] | null | undefined): Record<number, string | null> {
  const out: Record<number, string | null> = {};
  (blocks ?? []).forEach((b, i) => {
    if (b.type !== "equation" || typeof b.latex !== "string") return;
    try {
      // BOOK-CORRECTION-01: a printed error inside the formula is typeset in red.
      const latex = markLatex(b.latex, bookErrors(b.book_errors));
      out[i] = paintBookErrors(katex.renderToString(latex, { ...KATEX_OPTIONS, displayMode: b.display !== false }));
    } catch {
      out[i] = null;
    }
  });
  return out;
}
