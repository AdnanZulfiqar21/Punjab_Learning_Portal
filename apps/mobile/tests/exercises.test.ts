// BOOK-EXERCISES-01: the end-of-chapter exercise is Practice, not Learn (src/lib/exercises.ts). Host-side tests; not
// device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { exerciseStatus, exerciseTitle, learnTopics, mcqTitle, practiceChapters, practiceOnly, practiceTitle, revealLabel, shortTitle, longTitle } from "../src/lib/exercises.ts";

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

  it("lists a chapter's MCQs in Practice beside its exercise, by chapter", () => {
    assert.equal(practiceOnly("mcq"), true);
    assert.equal(practiceTitle({ kind: "mcq", title: "MCQs", chapter_number: 1 }), "Chapter 1 · MCQs");
    assert.equal(mcqTitle("Unit", 3), "Unit 3 · MCQs");
    const item = (id: string, n: number) => ({ topic_id: id, chapter_number: n, chapter_title: `Ch ${n}`, availability: "published", available_languages: ["en"] });
    const chapters = practiceChapters({ exercises: [item("e2", 2), item("e1", 1)], mcq_sets: [item("m1", 1), item("m3", 3)] });
    assert.deepEqual(
      chapters.map((c) => [c.number, c.exercise?.topic_id, c.mcqs?.topic_id]),
      [[1, "e1", "m1"], [2, "e2", undefined], [3, undefined, "m3"]],
    );
    assert.deepEqual(practiceChapters({ exercises: [] }), []);
    // PRACTICE-SHORT-01: short questions sit beside the MCQs in the same chapter.
    assert.equal(practiceOnly("short"), true);
    assert.equal(practiceTitle({ kind: "short", title: "Short Questions", chapter_number: 1 }), "Chapter 1 · Short Questions");
    assert.equal(shortTitle("Unit", 2), "Unit 2 · Short Questions");
    const withShorts = practiceChapters({ exercises: [item("e1", 1)], mcq_sets: [item("m1", 1)], short_sets: [item("s1", 1), item("s4", 4)] });
    assert.deepEqual(
      withShorts.map((c) => [c.number, c.mcqs?.topic_id, c.shorts?.topic_id]),
      [[1, "m1", "s1"], [4, undefined, "s4"]],
    );
    // PRACTICE-LONG-01: long questions sit beside them too.
    assert.equal(practiceOnly("long"), true);
    assert.equal(practiceTitle({ kind: "long", title: "Long Questions", chapter_number: 1 }), "Chapter 1 · Long Questions");
    assert.equal(longTitle("Unit", 3), "Unit 3 · Long Questions");
    const withLongs = practiceChapters({ exercises: [], short_sets: [item("s1", 1)], long_sets: [item("l1", 1), item("l2", 2)] });
    assert.deepEqual(
      withLongs.map((c) => [c.number, c.shorts?.topic_id, c.longs?.topic_id]),
      [[1, "s1", "l1"], [2, undefined, "l2"]],
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
