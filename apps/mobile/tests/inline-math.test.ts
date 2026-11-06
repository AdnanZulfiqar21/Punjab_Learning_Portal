// INLINE-MATH-01: formulas in lesson text read as plain text in the apps, which have no equation renderer yet
// (src/lib/inline-math.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { hasMath, latexToText, plainMath } from "../src/lib/inline-math.ts";

describe("latexToText", () => {
  it("writes fractions, roots and powers readably", () => {
    assert.equal(latexToText("\\frac{-27}{41}-\\frac{38}{41}i"), "(-27)/41-38/41i");
    assert.equal(latexToText("\\sqrt{x^{2}+y^{2}}"), "√(x²+y²)");
    assert.equal(latexToText("i^{19}"), "i¹⁹");
    assert.equal(latexToText("z_{1}\\cdot z_{2}"), "z₁·z₂");
  });

  it("keeps Greek letters, operators and functions", () => {
    assert.equal(latexToText("1+\\omega+\\omega^{2}=0"), "1+ω+ω²=0");
    assert.equal(latexToText("r(\\cos\\theta+i\\sin\\theta)"), "r(cos θ+isin θ)");
    assert.equal(latexToText("\\operatorname{Re}(z)\\Rightarrow a"), "Re(z)⇒a");
  });

  it("marks a conjugate with a bar over one letter", () => {
    assert.equal(latexToText("\\overline{z}"), "z̅");
  });
});

describe("plainMath", () => {
  it("leaves text without formulas untouched", () => {
    assert.equal(plainMath("No formula here (none)."), "No formula here (none).");
    assert.equal(hasMath("a (b) [c]"), false);
  });

  it("replaces inline and display formulas", () => {
    assert.equal(plainMath("So \\(z=a+ib\\) is complex."), "So z=a+ib is complex.");
    assert.equal(plainMath("Work:\n\\[x^{2}=4\\]\nWhy: square."), "Work:\nx²=4\nWhy: square.");
  });
});

describe("stepText", () => {
  it("drops a written step number the list already draws", async () => {
    const { stepText } = await import("../src/lib/solved-labels.ts");
    assert.equal(stepText("Step 2: Multiply by the conjugate"), "Multiply by the conjugate");
    assert.equal(stepText("Qadam 3. Upar expand karein"), "Upar expand karein");
    assert.equal(stepText("Check: substitute back"), "Check: substitute back");
  });
});
