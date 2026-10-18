// Lesson tables on a phone (renderer 2): a comparison table becomes one card per row, so a 5-column table such as
// "Membrane lipids compared" reads top to bottom instead of being cut off at the screen edge. Pure for tests.

export type ComparisonCard = { title: string; fields: { label: string; value: string }[] };

/**
 * Rows as cards: the first column names the card, the other columns become label/value lines under it. A table with a
 * single column, or none, has nothing to compare and is left to the plain layout (`null`).
 */
export function comparisonCards(header: readonly string[], rows: readonly (readonly string[])[]): ComparisonCard[] | null {
  if (header.length < 2 || rows.length === 0) return null;
  return rows.map((row, i) => ({
    title: row[0]?.trim() || `Row ${i + 1}`,
    fields: header.slice(1).map((label, j) => ({ label: label.trim() || `Column ${j + 2}`, value: row[j + 1] ?? "" })),
  }));
}
