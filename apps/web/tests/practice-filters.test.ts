// DESIGN-01 (Practice pages): the class and subject pill filters. Host-side tests of src/lib/practice-filters.ts.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { filterHref, taughtSubjects } from "../src/lib/practice-filters.ts";

const ALL: [string, string][] = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
];

describe("taughtSubjects", () => {
  it("leaves Mathematics out (not taught, owner 2026-10-19) and keeps the others in order", () => {
    assert.deepEqual(
      taughtSubjects(ALL).map(([c]) => c),
      ["biology", "chemistry", "physics", "computer_science"],
    );
  });

  it("does not change the list it is given", () => {
    const copy = ALL.map((s) => [...s]);
    taughtSubjects(ALL);
    assert.deepEqual(ALL, copy);
  });
});

describe("filterHref", () => {
  it("links a page to one class and subject", () => {
    assert.equal(filterHref("/practice", 11, "biology"), "/practice?grade=11&subject=biology");
    assert.equal(filterHref("/practice/exercises", 12, "computer_science"), "/practice/exercises?grade=12&subject=computer_science");
  });
});
