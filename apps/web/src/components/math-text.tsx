import katex from "katex";
import "katex/dist/katex-swap.min.css";
import { Fragment } from "react";
import { mathPieces } from "@/lib/inline-math";
import { KATEX_OPTIONS } from "@/lib/katex-options";

// INLINE-MATH-01: a sentence with formulas typeset where they stand (KaTeX, the options every equation uses). The
// typeset copy carries its own MathML for screen readers. A formula that can't be typeset shows its LaTeX as written,
// never an empty gap. A line of its own (\[ … \]) scrolls sideways on a narrow phone instead of widening the page.
export function MathText({ text }: { text: string }) {
  return (
    <>
      {mathPieces(text).map((p, i, all) => {
        if (p.kind === "text") {
          // A line of its own already starts and ends a line: the line breaks written around it would add blank lines.
          let t = p.text;
          const prevLine = all[i - 1]?.kind === "math" && (all[i - 1] as { display: boolean }).display;
          const nextLine = all[i + 1]?.kind === "math" && (all[i + 1] as { display: boolean }).display;
          if (prevLine) t = t.replace(/^[ \t]*\n/, "");
          if (nextLine) t = t.replace(/\n[ \t]*$/, "");
          return <Fragment key={i}>{t}</Fragment>;
        }
        let html: string | null = null;
        try {
          html = katex.renderToString(p.latex, { ...KATEX_OPTIONS, displayMode: p.display });
        } catch {
          html = null;
        }
        if (html === null)
          return (
            <code key={i} className="font-mono text-[0.9em]">
              {p.latex}
            </code>
          );
        return <span key={i} className={p.display ? "math-display" : "math-inline"} dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </>
  );
}
