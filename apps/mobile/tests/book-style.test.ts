// BOOK-STYLE-01: the premium style of a chosen book (src/lib/book-style.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { leadIn, leadTerm, premiumBook } from "../src/lib/book-style.ts";

describe("premium book style", () => {
  it("is on for Class XI Computer Science only", () => {
    assert.equal(premiumBook("computer_science", 11), true);
    assert.equal(premiumBook("computer_science", 12), false);
    assert.equal(premiumBook("chemistry", 11), false);
    assert.equal(premiumBook(null, null), false);
  });

  it("splits a list item at a short term and its colon", () => {
    assert.deepEqual(leadTerm("Interviews and Surveys: Asking questions."), ["Interviews and Surveys", "Asking questions."]);
    assert.deepEqual(leadTerm("Postfix Notation (Reverse Polish Notation, RPN): The operator is placed after."), [
      "Postfix Notation (Reverse Polish Notation, RPN)",
      "The operator is placed after.",
    ]);
    assert.equal(leadTerm("If you find an operator (like +, -, *), push it: done"), null); // more than six words
    assert.equal(leadTerm("In AB+, you first encounter A. Then: B"), null); // a sentence before the colon
    assert.equal(leadTerm("plain item without a term"), null);
  });

  it("keeps an item whole when the split would cut a book error", () => {
    assert.equal(leadTerm("Speed: fast and cheap", ["Speed: fast"]), null);
    assert.deepEqual(leadTerm("Speed: fast and cheap", ["cheap"]), ["Speed", "fast and cheap"]);
  });

  it("knows a lead-in line", () => {
    assert.equal(leadIn("Key activities in this phase include:"), true);
    assert.equal(leadIn("Example:"), true);
    assert.equal(leadIn("This is a sentence. It ends here:"), false);
    assert.equal(leadIn("A paragraph that does not end with a colon."), false);
  });

  it("is the same file in web and mobile", () => {
    const mobile = readFileSync(new URL("../src/lib/book-style.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/book-style.ts", import.meta.url), "utf8");
    assert.equal(mobile, web);
  });
});
