// INLINE-MATH-01 (MATHS-11-01): formulas inside lesson text, between \( \) or \[ \] (src/lib/inline-math.ts), and the
// Mathematics practice filters (src/lib/practice-filters.ts). Host-side tests.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { hasMath, mathPieces } from "../src/lib/inline-math.ts";
import { taughtSubjects } from "../src/lib/practice-filters.ts";
import { solvedLabels } from "../src/lib/solved-labels.ts";

describe("mathPieces", () => {
  it("leaves text without formulas as one plain piece", () => {
    assert.equal(hasMath("A sentence (with brackets) [and more]."), false);
    assert.deepEqual(mathPieces("A sentence."), [{ kind: "text", text: "A sentence." }]);
  });

  it("splits inline and display formulas in order", () => {
    assert.deepEqual(mathPieces("Let \\(z=a+ib\\). Then\n\\[|z|=\\sqrt{a^2+b^2}\\]\ndone"), [
      { kind: "text", text: "Let " },
      { kind: "math", latex: "z=a+ib", display: false },
      { kind: "text", text: ". Then\n" },
      { kind: "math", latex: "|z|=\\sqrt{a^2+b^2}", display: true },
      { kind: "text", text: "\ndone" },
    ]);
  });

  it("keeps an unclosed delimiter as plain text", () => {
    assert.deepEqual(mathPieces("cost \\( 5"), [{ kind: "text", text: "cost \\( 5" }]);
  });
});

describe("Mathematics exercises", () => {
  const ALL: [string, string][] = [
    ["physics", "Physics"],
    ["mathematics", "Mathematics"],
  ];

  it("offer no Mathematics question practice (its exercises are read in Learn)", () => {
    assert.deepEqual(taughtSubjects(ALL).map(([c]) => c), ["physics"]);
  });

  it("label a solved question in the lesson's language", () => {
    assert.equal(solvedLabels("roman_ur").answer, "Final jawab");
    assert.equal(solvedLabels("en").answer, "Final answer");
  });
});
