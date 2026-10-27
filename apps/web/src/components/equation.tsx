"use client";

import { type ReactNode, useEffect, useState } from "react";
import { paintBookErrors } from "@/lib/book-errors";
import { KATEX_OPTIONS } from "@/lib/katex-options";

// P01.S4.T2 (RENDERER-SPIKE-01): typeset equations and chemistry notation (mhchem `\ce{…}`) on the web.
//
// Server-rendered pages (lessons, topics, results, the notebook) typeset on the server (`lib/typeset.ts`), so they ship
// only KaTeX's CSS and the fonts a formula uses. Client-rendered surfaces (the exam runner, the studio) load KaTeX here
// when a formula needs it, after the page is shown: about 76 KB gzipped, plus 8 KB for chemistry.
//
// The reviewed static rendering stays in four cases: without JavaScript on those client surfaces, with data saver on
// (until asked), when a formula can't be typeset, and in the apps, which have no equation renderer yet. The typeset copy
// is hidden from screen readers, which read the reviewed text equivalent instead; once typeset, that equivalent is for
// screen readers only, so a displayed equation isn't printed twice (EQUATION-TEXT-01).

type Typeset = (latex: string, display: boolean) => string;
let loading: Promise<Typeset> | null = null;

function typesetter(): Promise<Typeset> {
  loading ??= Promise.all([import("katex"), import("katex/contrib/mhchem"), import("katex/dist/katex-swap.min.css")]).then(
    ([{ default: katex }]): Typeset =>
      (latex, display) =>
        paintBookErrors(katex.renderToString(latex, { ...KATEX_OPTIONS, displayMode: display })),
    (e: unknown) => {
      loading = null; // a failed download is retried by the next formula; a formula that fails to parse is not
      throw e;
    },
  );
  return loading;
}

export function Equation({
  latex,
  display,
  textAlt,
  textView,
  fallback,
  typeset,
  dataSaver = false,
}: {
  latex: string;
  display: boolean;
  textAlt: string;
  /** How the text equivalent is shown where the formula isn't typeset (e.g. with a book error marked). */
  textView?: ReactNode;
  /** The reviewed static rendering, if the block has one. */
  fallback: ReactNode;
  /** Typeset on the server: the markup, or null when it couldn't be typeset. Undefined: typeset here if needed. */
  typeset?: string | null;
  dataSaver?: boolean;
}) {
  const fromServer = typeset !== undefined;
  const [asked, setAsked] = useState(fromServer || !dataSaver);
  const [result, setResult] = useState<{ latex: string; html: string | null } | null>(null);
  useEffect(() => {
    if (fromServer || !asked) return;
    let live = true;
    typesetter()
      .then((t) => t(latex, display))
      .then(
        (html) => live && setResult({ latex, html }),
        () => live && setResult({ latex, html: null }),
      );
    return () => {
      live = false;
    };
  }, [fromServer, asked, latex, display]);

  const current = fromServer ? { latex, html: typeset } : result?.latex === latex ? result : null;
  if (current?.html) {
    return (
      <figure className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3" data-typeset="ok">
        <div aria-hidden="true" className="overflow-x-auto overflow-y-hidden py-1" dangerouslySetInnerHTML={{ __html: current.html }} />
        <figcaption className="sr-only">{textAlt}</figcaption>
      </figure>
    );
  }
  const failed = current !== null;
  return (
    <figure className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3" data-typeset={failed ? "failed" : asked ? "loading" : "off"}>
      {(failed || !asked) && fallback}
      <p>{textView ?? textAlt}</p>
      <figcaption className="font-mono text-xs text-muted">{latex}</figcaption>
      {!asked && (
        <button type="button" onClick={() => setAsked(true)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent">
          Typeset this formula (data saver is on)
        </button>
      )}
      {failed && <p className="text-xs text-muted">This formula couldn&apos;t be typeset here, so its reviewed rendering is shown.</p>}
    </figure>
  );
}
