# Scientific content rendering (P01.S4.T2, RENDERER-SPIKE-01)

This page records what the 2026-10-21 rendering spike proved on the web, what it measured, and what it left open.

## Safe content formats

- **Text blocks are plain text.** Headings, paragraphs, lists, callouts, tables and examples are rendered as text nodes and never as HTML.
  - The API stores no markup.
  - Text takes its direction from its own content (`dir="auto"`): an Urdu paragraph reads right to left, while English and Roman Urdu stay left to right.
- **Equations are LaTeX plus a reviewed text equivalent** (`text_alt`), with a reviewed static rendering as the fallback.
  - The web typesets them with KaTeX 0.19.0 (`apps/web/src/components/equation.tsx`), with the mhchem extension for chemistry (`\ce{2H2 + O2 -> 2H2O}`).
  - KaTeX runs with `trust: false`. `\href`, `\url`, `\includegraphics`, `\htmlClass`, `\htmlId`, `\htmlStyle` and `\htmlData` are shown as plain red command names, so a formula can't add a link, an element class, a style or an include.
  - It also runs with `maxSize: 10` and `maxExpand: 100`, which bounds what one formula can make the page do.
  - KaTeX emits only its own markup. The typeset copy is hidden from screen readers, which read the reviewed text equivalent instead.
- **Diagrams and figures are archived images** with alt text, optional long descriptions and captions (ASSETS-01). They are never executable SVG or HTML.

## Fallback rendering

The reviewed static rendering shows when:

- JavaScript is off;
- data saver is on (until the learner taps **Typeset this formula**);
- the formula can't be typeset;
- the reader is in the Android and iOS apps, which have no equation renderer yet.

A formula that fails to parse shows its reviewed image and a short note. The registry (`blocks.py`) still requires a reviewed fallback before an equation is published.

## Payload sizes (measured 2026-10-21)

| Part | Bytes | Gzipped | When it loads |
| --- | --- | --- | --- |
| `katex.min.js` | 272,868 | 75,906 | Only on a page with an equation, after the page is shown |
| `contrib/mhchem.min.js` | 33,706 | 8,392 | With KaTeX |
| `katex-swap.min.css` | 24,793 | 3,512 | With KaTeX (fonts use `font-display: swap`) |
| Fonts (20 woff2, all) | 259,792 | n/a (woff2) | Only the faces a formula uses; the fixture lesson used Main-Regular (26,272) and Math-Italic (16,440) |

Pages without equations load none of this. These figures come from the package's minified files. The development server's unminified chunks (about 330 KB) are not representative.

## Evidence

- `e2e/lessons.spec.ts` › "notation: formulas and chemistry are typeset safely, and Urdu reads right to left" uses the labelled `[FIXTURE] Notation lesson` from `portal-dev-seed-practice`. It checks that:
  - three formulas are typeset, and chemistry has real subscripts (MathML `msub`);
  - no `javascript:` link or injected class exists;
  - the unparsable formula shows its reviewed rendering;
  - the Urdu paragraph computes `direction: rtl`.
- The structured-blocks test now checks that the existing fixture formula is typeset with its text equivalent.
- The notation test passed locally against a development server on 2026-10-21. Screenshots at 1000 px and 375 px were taken the same day.
- Locally, the structured-blocks test stopped before its formula check: an archived diagram image did not load on that server. Two other lesson tests timed out signing up against the slow local API. Their result rests on CI.

## Not covered

- **Native typesetting (Android and iOS).** Equations reach the apps as their reviewed fallback, as before. A native equation renderer and its device check need B13 and B07.
- **Real owner-supplied equations.** No drafted lesson contains an equation block yet, so only technical fixtures were rendered.
- **An Urdu font choice (Nastaliq or Naskh).** The browser's system font was used.
- **Long MCQ options.** Options may now wrap inside the practice runner and results (`min-w-0 break-words`), but no fixture question with a long option was rendered.
