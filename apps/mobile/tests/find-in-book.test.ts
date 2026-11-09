// MCQ-BOOK-LINK-01: "See in book" marks the book's words a practice MCQ comes from (src/lib/find-in-book.ts). Host-side
// tests; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { findBlock, findRange } from "../src/lib/find-in-book.ts";

const PARA =
  "Physical quantities are often divided into two categories: base quantities and derived quantities. Derived quantities are those which depend on base quantities.";

describe("see in book", () => {
  it("marks the quoted words inside a paragraph", () => {
    const quote = "Derived quantities are those which depend on base quantities.";
    const [a, b] = findRange(PARA, quote)!;
    assert.equal(PARA.slice(a, b), quote);
  });

  it("matches across line breaks and doubled spaces", () => {
    const text = "The base  quantities are\nthe independent quantities.";
    const [a, b] = findRange(text, "base quantities are the independent")!;
    assert.equal(text.slice(a, b), "base  quantities are\nthe independent");
  });

  it("marks the quote's part when a paragraph is drawn in two pieces beside a figure", () => {
    const quote = "two categories: base quantities and derived quantities. Derived quantities are those";
    const head = PARA.slice(0, 80);
    const tail = PARA.slice(80);
    const [a, b] = findRange(head, quote)!;
    const [c, d] = findRange(tail, quote)!;
    assert.equal(head.slice(a, b) + tail.slice(c, d), quote);
  });

  it("marks nothing when the words are not there", () => {
    assert.equal(findRange(PARA, "Velocity is a vector quantity."), null);
    assert.equal(findRange(PARA, ""), null);
  });

  it("finds the block that holds the words, in its text, items or cells", () => {
    const blocks = [
      { type: "heading", text: "1.1 Physical quantities" },
      { type: "list", items: ["Length is a base quantity of the system."] },
      { type: "table", header: ["Quantity", "Unit"], rows: [["amount of substance", "mole"]] },
      { type: "paragraph", text: PARA },
    ];
    assert.equal(findBlock(blocks, "Derived quantities are those which depend"), 3);
    assert.equal(findBlock(blocks, "Length is a base quantity"), 1);
    assert.equal(findBlock(blocks, "amount of substance"), 2);
    assert.equal(findBlock(blocks, "nowhere in the lesson"), -1);
  });
});
