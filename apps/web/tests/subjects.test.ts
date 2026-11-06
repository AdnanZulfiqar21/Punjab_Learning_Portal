// The portal teaches Biology, Chemistry, Physics, Computer Science and Mathematics: the Class 11 Mathematics book since
// 2026-11-05 (MATHS-11-01) and the Class 12 one since 2026-11-06 (MATHS-12-01).
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { isTaught, taughtBooks, TAUGHT_SUBJECTS, tileGrade } from "../src/lib/subjects.ts";

describe("taught subjects", () => {
  it("are the five the portal teaches, in order", () => {
    assert.deepEqual(TAUGHT_SUBJECTS, ["biology", "chemistry", "physics", "computer_science", "mathematics"]);
  });

  it("teach Mathematics, like the other four", () => {
    assert.equal(isTaught("mathematics"), true);
    assert.equal(isTaught("physics"), true);
    assert.equal(isTaught("urdu"), false);
  });

  it("keep both Mathematics books and the rest, in order", () => {
    const books = [
      { subject: "mathematics", grade: 12 },
      { subject: "physics", grade: 11 },
      { subject: "mathematics", grade: 11 },
      { subject: "biology", grade: 12 },
    ];
    assert.deepEqual(taughtBooks(books), [
      { subject: "mathematics", grade: 12 },
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
