// BOOK-HEADING-01: a topic whose book text is only its heading continues with its first subtopic (src/lib/book-heading.ts).
// Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { continuesInto, headingOnly, isMainHeading } from "../src/lib/book-heading.ts";

const topic = (number: string, blocks: string[] | null, availability = "private_preview") => ({
  number,
  availability,
  next_topic_id: "next",
  lesson: blocks ? { body: { blocks: blocks.map((type) => ({ type })) } } : null,
});

describe("topics the book prints as a heading only", () => {
  it("knows a lesson of headings alone", () => {
    assert.equal(headingOnly(topic("14.4", ["heading"])), true);
    assert.equal(headingOnly(topic("14.4", ["heading", "paragraph"])), false);
    assert.equal(headingOnly(topic("14.4", [])), false);
    assert.equal(headingOnly(topic("14.4", null)), false);
  });

  it("continues only into its own subtopic that has a lesson", () => {
    const parent = topic("14.4", ["heading"]);
    assert.equal(continuesInto(parent, topic("14.4.1", ["paragraph"])), true);
    assert.equal(continuesInto(parent, topic("14.5", ["paragraph"])), false);
    assert.equal(continuesInto(parent, topic("14.40", ["paragraph"])), false);
    assert.equal(continuesInto(parent, topic("14.4.1", null)), false);
    assert.equal(continuesInto(parent, topic("14.4.1", ["paragraph"], "unavailable")), false);
  });
});

describe("book-heading helper", () => {
  it("is the same code on web and mobile", async () => {
    const { readFileSync } = await import("node:fs");
    const mobile = readFileSync(new URL("../src/lib/book-heading.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/book-heading.ts", import.meta.url), "utf8");
    assert.equal(web, mobile);
  });
});

describe("main headings", () => {
  it("are a chapter's numbered sections, not their subtopics", () => {
    for (const n of ["14.4", "2.9", "7.4", "33.7", "2.5b"]) assert.equal(isMainHeading(n), true, n);
    for (const n of ["14.4.1", "2.7.2b", "1.4.10", "", null, undefined]) assert.equal(isMainHeading(n), false, String(n));
  });
});
