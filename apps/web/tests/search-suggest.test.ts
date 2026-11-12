// SEARCH-SUGGEST-01: the search box's suggestions mark the typed text and open the right page.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { markTyped, suggestionHref } from "../src/lib/search-suggest.ts";

describe("search suggestions", () => {
  it("marks the typed text, whatever its case", () => {
    assert.deepEqual(markTyped("Biodegradable Polymers", "biodegra"), [
      { text: "Biodegra", match: true },
      { text: "dable Polymers", match: false },
    ]);
    assert.deepEqual(markTyped("Kinetic Molecular Theory", "  theory "), [
      { text: "Kinetic Molecular ", match: false },
      { text: "Theory", match: true },
    ]);
  });

  it("leaves a title found only by similarity unmarked", () => {
    assert.deepEqual(markTyped("Photosynthesis", "fotosynthesis"), [{ text: "Photosynthesis", match: false }]);
  });

  it("opens a topic itself and a chapter its chapter page", () => {
    assert.equal(suggestionHref({ kind: "topic", id: "t1", chapter_id: "c1" }), "/learn/topic/t1");
    assert.equal(suggestionHref({ kind: "chapter", id: "c1", chapter_id: "c1" }), "/learn/chapter/c1");
  });
});
