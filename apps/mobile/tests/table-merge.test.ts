// TABLE-MERGE-01: a printed table's merged cells (shell L over 2s and 2p), drawn as one cell on wide screens and
// repeated in each phone card (src/lib/table-merge.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { fillMerged, mergedColumns, mergeStarts, rowSpans } from "../src/lib/table-merge.ts";

// Shaped like Chemistry 11 Table 2.4: shell and n merged down, subshells one per row.
const rows = [
  ["K", "1", "0", "1s", "1"],
  ["L", "2", "0", "2s", "2"],
  ["", "", "1", "2p", ""],
  ["M", "3", "0", "3s", "3"],
  ["", "", "1", "3p", ""],
  ["", "", "2", "3d", ""],
];
const cols = [0, 1, 4];

describe("merged table cells", () => {
  it("spans each merged cell over the blank cells below it", () => {
    const spans = rowSpans(rows, cols);
    assert.deepEqual(spans.map((r) => r[0]), [1, 2, 0, 3, 0, 0]);
    assert.deepEqual(spans.map((r) => r[4]), [1, 2, 0, 3, 0, 0]);
    assert.deepEqual(spans.map((r) => r[3]), [1, 1, 1, 1, 1, 1]); // not merged: every cell its own
  });

  it("repeats the merged value in every row for phone cards", () => {
    const filled = fillMerged(rows, cols);
    assert.deepEqual(filled.map((r) => r[0]), ["K", "L", "L", "M", "M", "M"]);
    assert.deepEqual(filled[5], ["M", "3", "2", "3d", "3"]);
    assert.deepEqual(rows[2], ["", "", "1", "2p", ""]); // the input is untouched
  });

  it("leaves a blank at the top of a column and unmerged columns alone", () => {
    assert.deepEqual(rowSpans([["", "a"], ["", "b"]], [0]).map((r) => r[0]), [1, 1]);
    assert.deepEqual(fillMerged([["x", ""], ["", ""]], [0]), [["x", ""], ["x", ""]]);
    assert.deepEqual(mergedColumns([0, "1", -1, 2.5, 3]), [0, 3]);
  });

  it("starts a new, empty cell where the book leaves one under a merged cell", () => {
    // Shaped like Table 10.2's Trend column: the arrow covers the first rows; the reference row has its own empty cell
    // and the last rows share another.
    const trend = [["Li", "arrow"], ["K", ""], ["H2", ""], ["Cu", ""], ["Hg", ""]];
    const starts = mergeStarts([[2, 1], [3, 1], ["4", 1]]);
    assert.deepEqual([...starts], ["2:1", "3:1"]);
    assert.deepEqual(rowSpans(trend, [1], starts).map((r) => r[1]), [2, 0, 1, 2, 0]);
    assert.deepEqual(fillMerged(trend, [1], starts).map((r) => r[1]), ["arrow", "arrow", "", "", ""]);
  });

  it("is the same code on web and mobile", () => {
    const mobile = readFileSync(new URL("../src/lib/table-merge.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/table-merge.ts", import.meta.url), "utf8");
    assert.equal(web, mobile);
  });
});
