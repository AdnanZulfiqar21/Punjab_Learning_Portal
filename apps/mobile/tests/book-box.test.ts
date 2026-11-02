// BOOK-BOX-01: the book's printed boxes ("Do You Know?", "Thumb Rule", "Brain Teaser" …) keep the book's look: a coloured
// header for each kind, and a short box sits at the side of the text on wide screens (src/lib/book-box.ts).
// Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BOOK_BOX_KINDS, bookBoxKind, boxRow, boxRun, isBookBox, isMarginNote, sideBox, sideOrder } from "../src/lib/book-box.ts";

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
    assert.equal(bookBoxKind("Quick Check 3.2"), "check");
    assert.equal(bookBoxKind("Self-Assessment"), "check");
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

  it("knows a printed box and a run of boxes next to each other", () => {
    const box = { type: "callout", tone: "note", title: "For your information", text: "x" };
    const para = { type: "paragraph", text: "x" };
    const tip = { type: "callout", tone: "tip", title: "Diagram ko samjhein", text: "x" };
    assert.equal(isBookBox(box), true);
    assert.equal(isBookBox(tip), false);
    assert.equal(isBookBox({ type: "callout", tone: "note", text: "x" }), false); // an untitled note is not a printed box
    const blocks = [para, box, box, para, box, box, box, tip];
    assert.deepEqual(blocks.map((_, i) => boxRun(blocks, i)), [0, 2, 0, 0, 3, 0, 0, 0]);
  });

  it("knows a margin note the book prints without a title", () => {
    assert.equal(isMarginNote({ type: "callout", tone: "note", text: "x" }), true);
    assert.equal(isMarginNote({ type: "callout", text: "x" }), true); // tone defaults to note
    assert.equal(isMarginNote({ type: "callout", tone: "note", title: "  ", text: "x" }), true);
    assert.equal(isMarginNote({ type: "callout", tone: "note", title: "Do You Know?", text: "x" }), false); // a printed box
    assert.equal(isMarginNote({ type: "callout", tone: "tip", text: "x" }), false); // our own tip
    assert.equal(isMarginNote({ type: "paragraph", text: "x" }), false);
  });

  it("draws a side box before the text in front of it when no text follows it", () => {
    const box = { type: "callout", tone: "note", title: "Recalling", text: "short" };
    const note = { type: "callout", tone: "note", text: "short" };
    const para = { type: "paragraph", text: "x" };
    const fig = { type: "diagram", alt: "x" };
    assert.deepEqual(sideOrder([para, box, fig]), [1, 0, 2]); // the paragraph flows beside the box
    assert.deepEqual(sideOrder([para, note]), [1, 0]); // lesson ends after the note
    assert.deepEqual(sideOrder([para, box, para]), [0, 1, 2]); // text already follows the box
    assert.deepEqual(sideOrder([fig, box, fig]), [0, 1, 2]); // no text before it either
    assert.deepEqual(sideOrder([para, box, box, fig]), [0, 1, 2, 3]); // a row of boxes is not moved
    const long = { type: "callout", tone: "note", title: "Recalling", text: "x".repeat(421) };
    assert.deepEqual(sideOrder([para, long, fig]), [0, 1, 2]); // a long box is full width, nothing to flow beside
  });

  it("puts a run side by side only when no text would flow beside it", () => {
    const box = { type: "callout", tone: "note", title: "For your information", text: "x" };
    const para = { type: "paragraph", text: "x" };
    const fig = { type: "diagram", alt: "x" };
    assert.equal(boxRow([para, box, box], 1), 2); // lesson ends after the boxes
    assert.equal(boxRow([para, box, box, fig], 1), 2); // a figure follows: nothing flows beside
    assert.equal(boxRow([para, box, box, para], 1), 0); // text follows: it flows beside the boxes in the margin
    assert.equal(boxRow([para, box, box, { type: "heading", text: "x" }], 1), 0);
    assert.equal(boxRow([para, box, para], 1), 0); // a single box stays in the margin
  });

  it("is the same file on web and app", async () => {
    const { readFileSync } = await import("node:fs");
    const mobile = readFileSync(new URL("../src/lib/book-box.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/book-box.ts", import.meta.url), "utf8");
    assert.equal(mobile, web);
  });
});
