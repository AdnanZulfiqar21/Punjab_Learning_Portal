import type { KatexOptions } from "katex";

// P01.S4.T2 (RENDERER-SPIKE-01): one set of KaTeX options for the server and the browser. `trust: false` shows \href,
// \url, \includegraphics and the \html… commands as plain red command names, so a formula can't add a link, an element
// class, a style or an include; `maxSize` and `maxExpand` bound what one formula can make the page do.
export const KATEX_OPTIONS: KatexOptions = {
  output: "htmlAndMathml",
  throwOnError: true,
  trust: false,
  strict: "ignore",
  maxSize: 10,
  maxExpand: 100,
};
