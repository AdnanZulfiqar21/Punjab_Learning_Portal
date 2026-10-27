// TABLE-MERGE-01: a printed table often merges a cell down over several rows (shell L over 2s and 2p). A table block
// names those columns in `merged_columns`; there, a blank cell continues the cell above it. `merge_starts` lists the
// [row, column] cells that begin a new cell although blank (the book's empty cell under a merged one). Wide screens
// draw the run as one cell (rowSpan); phone cards repeat the value in every row so each card stays complete.
// Identical in apps/web and apps/mobile (a host test compares the two files).

export function mergedColumns(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((c): c is number => Number.isInteger(c) && c >= 0) : [];
}

/** The `merge_starts` cells as "row:column" keys. */
export function mergeStarts(v: unknown): Set<string> {
  const out = new Set<string>();
  if (!Array.isArray(v)) return out;
  for (const p of v) {
    if (Array.isArray(p) && p.length === 2 && p.every((n) => Number.isInteger(n) && n >= 0)) out.add(`${p[0]}:${p[1]}`);
  }
  return out;
}

/** For each cell: its row span (≥ 1) where a cell is drawn, or 0 where it is covered by the merged cell above. */
export function rowSpans(
  rows: readonly (readonly string[])[],
  cols: readonly number[],
  starts: ReadonlySet<string> = new Set(),
): number[][] {
  const spans = rows.map((r) => r.map(() => 1));
  for (const c of cols) {
    let start = -1;
    for (let r = 0; r < rows.length; r++) {
      if (c >= rows[r].length) continue;
      const begins = Boolean(rows[r][c].trim()) || starts.has(`${r}:${c}`);
      if (!begins && start >= 0) {
        spans[start][c] += 1;
        spans[r][c] = 0;
      } else {
        start = begins ? r : -1;
      }
    }
  }
  return spans;
}

/** Rows with every covered cell of a merged column filled from the cell that covers it (for phone cards). */
export function fillMerged(
  rows: readonly (readonly string[])[],
  cols: readonly number[],
  starts: ReadonlySet<string> = new Set(),
): string[][] {
  const spans = rowSpans(rows, cols, starts);
  const out = rows.map((r) => [...r]);
  for (let r = 1; r < out.length; r++) {
    for (let c = 0; c < out[r].length; c++) if (spans[r][c] === 0) out[r][c] = out[r - 1][c];
  }
  return out;
}
