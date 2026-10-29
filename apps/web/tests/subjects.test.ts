// The portal teaches four subjects; Mathematics books are indexed but not taught (owner, 2026-10-19).
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { taughtBooks, TAUGHT_SUBJECTS } from "../src/lib/subjects.ts";

describe("taught subjects", () => {
  it("are the four the portal teaches, in order", () => {
    assert.deepEqual(TAUGHT_SUBJECTS, ["biology", "chemistry", "physics", "computer_science"]);
  });

  it("leaves Mathematics books out and keeps the rest in order", () => {
    const books = [{ subject: "mathematics" }, { subject: "physics" }, { subject: "biology" }];
    assert.deepEqual(taughtBooks(books), [{ subject: "physics" }, { subject: "biology" }]);
  });
});
