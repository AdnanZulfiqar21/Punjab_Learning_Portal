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

describe("Mathematics exercises (MATHS-11-01)", () => {
  it("are listed for Class 11 only, titled by their own number, with the video view", async () => {
    const { exerciseSubjects, hasVideoSolutions, practiceTitle } = await import("../src/lib/exercises.ts");
    const all = [["physics", "Physics"], ["mathematics", "Mathematics"]] as const;
    assert.deepEqual(exerciseSubjects(all, 11).map(([c]) => c), ["physics", "mathematics"]);
    assert.deepEqual(exerciseSubjects(all, 12).map(([c]) => c), ["physics"]);
    assert.equal(practiceTitle({ kind: "exercise", title: "Exercise 1.5", chapter_number: 1 }), "Exercise 1.5");
    assert.equal(hasVideoSolutions("mathematics", "exercise"), true);
    assert.equal(hasVideoSolutions("mathematics", "topic"), false);
    assert.equal(hasVideoSolutions("physics", "exercise"), false);
  });
});
