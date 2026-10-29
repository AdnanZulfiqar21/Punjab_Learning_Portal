// BOOK-BOX-01: the book's printed boxes ("Do You Know?", "Thumb Rule", "Brain Teaser" …) keep the book's look: a coloured
// header for each kind, and a short box sits at the side of the text on wide screens (src/lib/book-box.ts).
// Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BOOK_BOX_KINDS, bookBoxKind, sideBox } from "../src/lib/book-box.ts";

describe("book boxes", () => {
  it("know their kind from the printed title, in English or Roman Urdu", () => {
    assert.equal(bookBoxKind("Thumb Rule for Uncertainty"), "rule");
    assert.equal(bookBoxKind("Remember Thumb Rule"), "rule");
    assert.equal(bookBoxKind("Do You Know?"), "know");
    assert.equal(bookBoxKind("Did you Know!"), "know");
    assert.equal(bookBoxKind("Kya aap jante hain? (Do You Know?)"), "know");
    assert.equal(bookBoxKind("For Your Information"), "info");
    assert.equal(bookBoxKind("Aap ki maloomat ke liye"), "info");
    assert.equal(bookBoxKind("Interesting Information!"), "interesting");
    assert.equal(bookBoxKind("Dilchasp maloomat"), "interesting");
    assert.equal(bookBoxKind("Fascinating Fact"), "interesting");
    assert.equal(bookBoxKind("Tid-bits"), "tidbit");
    assert.equal(bookBoxKind("Tidbit!"), "tidbit");
    assert.equal(bookBoxKind("Point to ponder"), "ponder");
    assert.equal(bookBoxKind("Ponder Upon"), "ponder");
    assert.equal(bookBoxKind("Brain Teaser!"), "teaser");
    assert.equal(bookBoxKind("Quick Quiz"), "quiz");
    assert.equal(bookBoxKind("Keep in Mind!"), "keep");
    assert.equal(bookBoxKind("Class Activity"), "activity");
    assert.equal(bookBoxKind("A Scientific Fact"), "fact");
    assert.equal(bookBoxKind("Interesting Application"), "fact");
    assert.equal(bookBoxKind("Significance of Archaea"), "info"); // any other printed box
  });

  it("gives the common kinds different colours", () => {
    assert.equal(new Set(BOOK_BOX_KINDS).size, BOOK_BOX_KINDS.length);
    assert.ok(BOOK_BOX_KINDS.length >= 10);
  });

  it("puts only a short box at the side", () => {
    assert.equal(sideBox("Mean deviation from an average value."), true);
    assert.equal(sideBox("x".repeat(420)), true);
    assert.equal(sideBox("x".repeat(421)), false);
  });

  it("is the same file on web and app", async () => {
    const { readFileSync } = await import("node:fs");
    const mobile = readFileSync(new URL("../src/lib/book-box.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/book-box.ts", import.meta.url), "utf8");
    assert.equal(mobile, web);
  });
});
