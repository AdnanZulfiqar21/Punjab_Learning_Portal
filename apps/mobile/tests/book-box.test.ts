// BOOK-BOX-01: the book's printed boxes ("Do You Know?", "Thumb Rule", "Brain Teaser" …) keep the book's look: a coloured
// header for each kind, and a short box sits at the side of the text on wide screens (src/lib/book-box.ts).
// Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { bookBoxKind, sideBox } from "../src/lib/book-box.ts";

describe("book boxes", () => {
  it("know their kind from the printed title, in English or Roman Urdu", () => {
    assert.equal(bookBoxKind("Thumb Rule for Uncertainty"), "rule");
    assert.equal(bookBoxKind("Remember Thumb Rule"), "rule");
    assert.equal(bookBoxKind("Do You Know?"), "know");
    assert.equal(bookBoxKind("Did you Know!"), "know");
    assert.equal(bookBoxKind("Kya aap jante hain? (Do You Know?)"), "know");
    assert.equal(bookBoxKind("For Your Information"), "info");
    assert.equal(bookBoxKind("Interesting Information!"), "info");
    assert.equal(bookBoxKind("Tid-bits"), "info");
    assert.equal(bookBoxKind("Brain Teaser!"), "ponder");
    assert.equal(bookBoxKind("Point to ponder"), "ponder");
    assert.equal(bookBoxKind("Quick Quiz"), "ponder");
    assert.equal(bookBoxKind("Keep in Mind!"), "keep");
    assert.equal(bookBoxKind("Class Activity"), "activity");
    assert.equal(bookBoxKind("Significance of Archaea"), "info"); // any other printed box
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
