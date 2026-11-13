// BOOK-LIST-01: list labels as the book prints them (src/lib/book-list.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import {
  isListMarker,
  labelWidth,
  listLabel,
  splitLabel,
} from "../src/lib/book-list.ts";

describe("book list labels", () => {
  it("counts in the book's style", () => {
    assert.equal(listLabel("i-", 3), "iii-");
    assert.equal(listLabel("i-", 4), "iv-");
    assert.equal(listLabel("(a)", 2), "(b)");
    assert.equal(listLabel("a)", 27), "aa)");
    assert.equal(listLabel("1-", 12), "12-");
    assert.equal(listLabel("(1)", 3), "(3)");
    assert.equal(listLabel("A.", 3), "C.");
    assert.equal(listLabel("(I)", 9), "(IX)");
  });

  it("knows the allowed markers", () => {
    assert.equal(isListMarker("i-"), true);
    assert.equal(isListMarker("(a)"), true);
    assert.equal(isListMarker("*"), false);
    assert.equal(isListMarker(undefined), false);
  });

  it("sizes the label column to the longest label", () => {
    assert.equal(labelWidth("i-", 1, 4), 5); // "iii-" plus a space
    assert.equal(labelWidth("(a)", 1, 6), 4);
  });

  it("finds a label at the start of a paragraph", () => {
    assert.deepEqual(splitLabel("(a) In electroporation, pores are created."), [
      "(a)",
      "In electroporation, pores are created.",
    ]);
    assert.deepEqual(splitLabel("ii- Epinephrine is released."), [
      "ii-",
      "Epinephrine is released.",
    ]);
    assert.deepEqual(splitLabel("3- Uric acid"), ["3-", "Uric acid"]);
    assert.deepEqual(splitLabel("b) Proximal tubule"), [
      "b)",
      "Proximal tubule",
    ]);
    assert.equal(splitLabel("1. 5 g of salt"), null); // a number, not a label
    assert.equal(splitLabel("In electroporation (a) pores"), null);
    assert.equal(splitLabel("(a)"), null); // nothing after the label
    assert.equal(splitLabel("(a) wrong text", ["(a) wrong"]), null); // a book error across the label stays whole
  });

  it("is the same file in web and mobile", () => {
    const mobile = readFileSync(
      new URL("../src/lib/book-list.ts", import.meta.url),
      "utf8",
    );
    const web = readFileSync(
      new URL("../../web/src/lib/book-list.ts", import.meta.url),
      "utf8",
    );
    assert.equal(mobile, web);
  });
});
