// INLINE-MATH-01 (MATHS-11-01): formulas inside lesson text, between \( \) or \[ \] (src/lib/inline-math.ts), and the
// Mathematics book exercises (src/lib/practice-filters.ts, src/lib/exercises.ts). Host-side tests.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { practiceTitle } from "../src/lib/exercises.ts";
import { hasMath, mathPieces } from "../src/lib/inline-math.ts";
import { exerciseSubjects, taughtSubjects } from "../src/lib/practice-filters.ts";
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

  it("offer Mathematics book exercises in Class 11 only, and no Mathematics question practice", () => {
    assert.deepEqual(exerciseSubjects(ALL, 11).map(([c]) => c), ["physics", "mathematics"]);
    assert.deepEqual(exerciseSubjects(ALL, 12).map(([c]) => c), ["physics"]);
    assert.deepEqual(taughtSubjects(ALL).map(([c]) => c), ["physics"]);
  });

  it("title a numbered exercise by its own number and a chapter's single exercise by the chapter", () => {
    assert.equal(practiceTitle({ kind: "exercise", title: "Exercise 1.3", chapter_number: 1 }), "Exercise 1.3");
    assert.equal(practiceTitle({ kind: "exercise", title: "Exercise", chapter_number: 2 }), "Chapter 2 · Exercise");
  });

  it("label a solved question in the lesson's language", () => {
    assert.equal(solvedLabels("roman_ur").answer, "Final jawab");
    assert.equal(solvedLabels("en").answer, "Final answer");
  });
});
