// BOOK-HEADING-01: where the book prints only a topic's heading and runs straight into its first subtopic (Chemistry
// 11 14.4 into 14.4.1), the reader goes on with that subtopic under its own heading instead of an empty page.

type Reading = {
  number: string | null;
  availability: string;
  next_topic_id: string | null;
  lesson: { body: { [key: string]: unknown } | null } | null;
};

/** A main heading of the chapter (14.4), not a subtopic under one (14.4.1): it is shown in the accent colour, every
 * other heading in the text colour (owner, 2026-10-27). */
export function isMainHeading(number: string | null | undefined): boolean {
  return /^\d+\.\d+[a-z]?$/.test(number ?? "");
}

/** A heading's colour by its depth (owner, 2026-10-28, after Chemistry's three levels): a main heading (1.2, 14.4)
 * takes the subject accent, a topic under it (1.2.2, 14.4.1) the text colour, and anything deeper (1.2.2.1) the
 * subheading blue, as the headings inside a Chemistry lesson. */
export function headingTone(number: string | null | undefined): "main" | "topic" | "sub" | null {
  const n = (number ?? "").trim();
  if (!/^\d+(\.\d+)+[a-z]?$/i.test(n)) return null;
  const depth = n.split(".").length;
  return depth <= 2 ? "main" : depth === 3 ? "topic" : "sub";
}

/** The lesson is the book's heading alone, so the page should continue with the next topic if it is a subtopic. */
export function headingOnly(reading: Reading): boolean {
  const blocks = reading.lesson?.body?.blocks;
  return Array.isArray(blocks) && blocks.length > 0 && blocks.every((b) => (b as { type?: unknown })?.type === "heading");
}

/** The next topic is this topic's own subtopic (14.4.1 under 14.4) and has a lesson to show. */
export function continuesInto(reading: Reading, next: Reading): boolean {
  return (
    Boolean(reading.number) &&
    Boolean(next.number?.startsWith(`${reading.number}.`)) &&
    next.availability !== "unavailable" &&
    Boolean(next.lesson?.body)
  );
}
