// The portal teaches Biology, Chemistry, Physics and Computer Science, and (MATHS-11-01, owner 2026-11-05) the Class 11
// Mathematics book; the Class 12 Mathematics book stays out of learner pages.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { isTaught, taughtBooks, TAUGHT_SUBJECTS, tileGrade } from "../src/lib/subjects.ts";

describe("taught subjects", () => {
  it("are the five the portal teaches, in order", () => {
    assert.deepEqual(TAUGHT_SUBJECTS, ["biology", "chemistry", "physics", "computer_science", "mathematics"]);
  });

  it("teach Mathematics in Class 11 only", () => {
    assert.equal(isTaught("mathematics", 11), true);
    assert.equal(isTaught("mathematics", 12), false);
    assert.equal(isTaught("physics", 12), true);
  });

  it("keep the Class 11 Mathematics book, leave the Class 12 one out, and keep the rest in order", () => {
    const books = [
      { subject: "mathematics", grade: 12 },
      { subject: "physics", grade: 11 },
      { subject: "mathematics", grade: 11 },
      { subject: "biology", grade: 12 },
    ];
    assert.deepEqual(taughtBooks(books), [
      { subject: "physics", grade: 11 },
      { subject: "mathematics", grade: 11 },
      { subject: "biology", grade: 12 },
    ]);
  });
});

describe("tile grade", () => {
  it("opens the learner's own class when the subject has it", () => {
    assert.equal(tileGrade([11, 12], 12), 12);
  });

  it("opens the first class when the learner has none or the subject lacks it", () => {
    assert.equal(tileGrade([11, 12], undefined), 11);
    assert.equal(tileGrade([12], 11), 12);
  });
});
