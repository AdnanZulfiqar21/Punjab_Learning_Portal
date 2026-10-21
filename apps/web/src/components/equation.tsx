"use client";

import { type ReactNode, useEffect, useState } from "react";

// P01.S4.T2 (RENDERER-SPIKE-01): typeset equations and chemistry notation (mhchem `\ce{…}`) on the web.
//
// KaTeX loads only on a page that has an equation, after the page is shown: about 76 KB gzipped, 8 KB more for
// chemistry, 3.5 KB of CSS and only the fonts the formula uses. Until it has loaded the text equivalent and the source
// show. The reviewed static rendering stays in four cases: without JavaScript, with data saver on (until asked), when the
// formula can't be typeset, and in the apps, which have no equation renderer yet.
//
// KaTeX runs with `trust: false`, so a formula can't add links, HTML, classes, styles or includes. It emits only its own
// markup. The typeset copy is hidden from screen readers, which read the reviewed text equivalent instead.

type Typeset = (latex: string, display: boolean) => string;
let loading: Promise<Typeset> | null = null;

function typesetter(): Promise<Typeset> {
  loading ??= Promise.all([import("katex"), import("katex/contrib/mhchem"), import("katex/dist/katex-swap.min.css")]).then(
    ([{ default: katex }]): Typeset =>
      (latex, display) =>
        katex.renderToString(latex, {
          displayMode: display,
          output: "htmlAndMathml",
          throwOnError: true,
          trust: false,
          strict: "ignore",
          maxSize: 10,
          maxExpand: 100,
        }),
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
  fallback,
  dataSaver = false,
}: {
  latex: string;
  display: boolean;
  textAlt: string;
  /** The reviewed static rendering, if the block has one. */
  fallback: ReactNode;
  dataSaver?: boolean;
}) {
  const [asked, setAsked] = useState(!dataSaver);
  const [result, setResult] = useState<{ latex: string; html: string | null } | null>(null);
  useEffect(() => {
    if (!asked) return;
    let live = true;
    typesetter()
      .then((typeset) => typeset(latex, display))
      .then(
        (html) => live && setResult({ latex, html }),
        () => live && setResult({ latex, html: null }),
      );
    return () => {
      live = false;
    };
  }, [asked, latex, display]);

  const current = result?.latex === latex ? result : null;
  if (current?.html) {
    return (
      <figure className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3" data-typeset="ok">
        <div aria-hidden="true" className="overflow-x-auto overflow-y-hidden py-1" dangerouslySetInnerHTML={{ __html: current.html }} />
        <figcaption>{textAlt}</figcaption>
      </figure>
    );
  }
  const failed = current !== null;
  return (
    <figure className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3" data-typeset={failed ? "failed" : asked ? "loading" : "off"}>
      {(failed || !asked) && fallback}
      <p>{textAlt}</p>
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
