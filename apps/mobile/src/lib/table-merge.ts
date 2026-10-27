// TABLE-MERGE-01: a printed table often merges a cell down over several rows (shell L over 2s and 2p). A table block
// names those columns in `merged_columns`; there, a blank cell continues the filled cell above it. Wide screens draw
// the run as one cell (rowSpan); phone cards repeat the value in every row so each card stays complete. Identical in
// apps/web and apps/mobile (a host test compares the two files).

export function mergedColumns(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((c): c is number => Number.isInteger(c) && c >= 0) : [];
}

/** Rows with every blank cell of a merged column filled from the filled cell above it (for phone cards). */
export function fillMerged(rows: readonly (readonly string[])[], cols: readonly number[]): string[][] {
  const out = rows.map((r) => [...r]);
  for (const c of cols) {
    for (let r = 1; r < out.length; r++) {
      if (c < out[r].length && !out[r][c].trim() && out[r - 1][c]?.trim()) out[r][c] = out[r - 1][c];
    }
  }
  return out;
}

/** For each cell: its row span (≥ 1) where a cell is drawn, or 0 where it is covered by the merged cell above. */
export function rowSpans(rows: readonly (readonly string[])[], cols: readonly number[]): number[][] {
  const spans = rows.map((r) => r.map(() => 1));
  for (const c of cols) {
    let start = -1;
    for (let r = 0; r < rows.length; r++) {
      if (c >= rows[r].length) continue;
      if (r > 0 && start >= 0 && !rows[r][c].trim()) {
        spans[start][c] += 1;
        spans[r][c] = 0;
      } else {
        start = rows[r][c].trim() ? r : -1;
      }
    }
  }
  return spans;
}
