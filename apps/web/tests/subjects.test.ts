// The portal teaches four subjects; Mathematics books are indexed but not taught (owner, 2026-10-19).
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { taughtBooks, TAUGHT_SUBJECTS, tileGrade } from "../src/lib/subjects.ts";

describe("taught subjects", () => {
  it("are the four the portal teaches, in order", () => {
    assert.deepEqual(TAUGHT_SUBJECTS, ["biology", "chemistry", "physics", "computer_science"]);
  });

  it("leaves Mathematics books out and keeps the rest in order", () => {
    const books = [{ subject: "mathematics" }, { subject: "physics" }, { subject: "biology" }];
    assert.deepEqual(taughtBooks(books), [{ subject: "physics" }, { subject: "biology" }]);
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
