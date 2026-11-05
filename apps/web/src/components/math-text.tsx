import { Fragment } from "react";
import { mathKey, mathPieces } from "@/lib/inline-math";

// INLINE-MATH-01: a sentence with formulas typeset where they stand. The formulas are typeset on the server
// (`lib/typeset.ts` `typesetMath`, the options every equation uses) and handed down as markup, so no page ships KaTeX's
// JavaScript for them (the payload budget). The typeset copy carries its own MathML for screen readers. A formula
// without markup (a surface that didn't typeset its lesson) shows its LaTeX as written, never an empty gap. A line of
// its own (\[ … \]) scrolls sideways on a narrow phone instead of widening the page.
export type MathHtml = Record<string, string | null>;

export function MathText({ text, html }: { text: string; html?: MathHtml }) {
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
        const markup = html?.[mathKey(p.latex, p.display)];
        if (!markup)
          return (
            <code key={i} className={`font-mono text-[0.9em] ${p.display ? "math-display" : ""}`}>
              {p.latex}
            </code>
          );
        return <span key={i} className={p.display ? "math-display" : "math-inline"} dangerouslySetInnerHTML={{ __html: markup }} />;
      })}
    </>
  );
}
