// BOOK-CORRECTION-01: the textbook's printed wording stays in the English lesson, and its wrong passages are marked
// (src/lib/book-errors.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { bookErrors, markLatex, markPieces, paintBookErrors } from "../src/lib/book-errors.ts";

describe("book error marks", () => {
  it("marks the printed passage and keeps the rest plain", () => {
    assert.deepEqual(markPieces("The range is 89.53 m.", ["89.53 m"]), [
      { text: "The range is ", error: false },
      { text: "89.53 m", error: true },
      { text: ".", error: false },
    ]);
  });

  it("marks every occurrence, and the longer of two marks starting together", () => {
    const pieces = markPieces("1/4 s after X and 1/4 s after Y", ["1/4", "1/4 s"]);
    assert.deepEqual(
      pieces.filter((p) => p.error).map((p) => p.text),
      ["1/4 s", "1/4 s"],
    );
    assert.equal(pieces.map((p) => p.text).join(""), "1/4 s after X and 1/4 s after Y");
  });

  it("leaves text without marks, or with marks it doesn't contain, as one plain piece", () => {
    assert.deepEqual(markPieces("Plain text.", []), [{ text: "Plain text.", error: false }]);
    assert.deepEqual(markPieces("Plain text.", ["absent"]), [{ text: "Plain text.", error: false }]);
  });

  it("reads only string marks from a block", () => {
    assert.deepEqual(bookErrors(["C10H14", 3, "", null]), ["C10H14"]);
    assert.deepEqual(bookErrors(undefined), []);
  });

  it("colours the printed error inside a formula once, and only marks that occur in it", () => {
    const latex = String.raw`\ce{2H2_{(g)} + 2NO_{(g)} -> N2_{(g)} + H2O_{(g)}}`;
    const marked = markLatex(latex, ["H2O_{(g)}", "H₂O(g)"]);
    // Inside \ce{…} the mark stays chemistry, so its subscripts survive the colour.
    assert.equal(marked, String.raw`\ce{2H2_{(g)} + 2NO_{(g)} -> N2_{(g)} + \textcolor{#a31d1e}{\ce{H2O_{(g)}}}}`);
    assert.equal(markLatex(latex, ["H₂O(g)"]), latex);
    assert.equal(markLatex(String.raw`K_p = K_n N^{\Delta n}`, ["K_n N"]), String.raw`K_p = \textcolor{#a31d1e}{K_n N}^{\Delta n}`);
    assert.equal(markLatex(String.raw`\text{rate} = k[\ce{H2}]`, ["k"]), String.raw`\text{rate} = \textcolor{#a31d1e}{k}[\ce{H2}]`);
    assert.equal(paintBookErrors('<span style="color:#a31d1e;">H</span>'), '<span style="color:var(--danger);background-color:var(--danger-soft);">H</span>');
  });

  it("is the same code on web and mobile", () => {
    const mobile = readFileSync(new URL("../src/lib/book-errors.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/book-errors.ts", import.meta.url), "utf8");
    assert.equal(web, mobile);
  });
});
