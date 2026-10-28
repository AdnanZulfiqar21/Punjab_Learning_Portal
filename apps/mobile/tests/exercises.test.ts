// BOOK-EXERCISES-01: the end-of-chapter exercise is Practice, not Learn (src/lib/exercises.ts). Host-side tests; not
// device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { exerciseStatus, exerciseTitle, learnTopics, revealLabel } from "../src/lib/exercises.ts";

describe("book exercises", () => {
  it("leaves the exercise out of Learn's topic list", () => {
    const topics = [{ id: "1.1", kind: "topic" }, { id: "1.2" }, { id: "ex", kind: "exercise" }];
    assert.deepEqual(
      learnTopics(topics).map((t) => t.id),
      ["1.1", "1.2"],
    );
  });

  it("names the exercise by its chapter", () => {
    assert.equal(exerciseTitle("Chapter", 2), "Chapter 2 · Exercise");
    assert.equal(exerciseTitle("Unit", 11), "Unit 11 · Exercise");
  });

  it("reveals answers in the lesson's language", () => {
    assert.equal(revealLabel("en"), "Show answer");
    assert.equal(revealLabel("roman_ur"), "Answer dekhein");
  });

  it("opens only an exercise that can be read", () => {
    assert.deepEqual(exerciseStatus("published", ["en", "roman_ur"]), { label: "English · Roman Urdu", open: true });
    assert.deepEqual(exerciseStatus("private_preview", ["en"]), { label: "Draft preview · English", open: true });
    assert.deepEqual(exerciseStatus("unavailable", []), { label: "Not ready yet", open: false });
  });
});
