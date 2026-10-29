// BOOK-EXERCISES-01: the end-of-chapter exercise is Practice, not Learn (src/lib/exercises.ts). Host-side tests; not
// device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { exerciseStatus, exerciseTitle, learnTopics, practiceOnly, practiceTitle, revealLabel } from "../src/lib/exercises.ts";

describe("book exercises", () => {
  it("leaves the exercise out of Learn's topic list", () => {
    const topics = [{ id: "1.1", kind: "topic" }, { id: "1.2" }, { id: "ex", kind: "exercise" }];
    assert.deepEqual(
      learnTopics(topics).map((t) => t.id),
      ["1.1", "1.2"],
    );
  });

  it("leaves the Board papers out of Learn too (BOOK-PAPERS-01)", () => {
    const topics = [{ id: "9.1", kind: "topic" }, { id: "ex", kind: "exercise" }, { id: "pp", kind: "paper" }, { id: "mp", kind: "paper" }];
    assert.deepEqual(
      learnTopics(topics).map((t) => t.id),
      ["9.1"],
    );
    assert.equal(practiceOnly(undefined), false);
    assert.equal(practiceOnly("topic"), false);
    assert.equal(practiceOnly("paper"), true);
  });

  it("names a Board paper by its own title and an exercise by its chapter", () => {
    assert.equal(practiceTitle({ kind: "paper", title: "Model Paper", chapter_number: 9 }), "Model Paper");
    assert.equal(practiceTitle({ kind: "exercise", title: "Exercise", chapter_number: 9 }), "Chapter 9 · Exercise");
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
