// BOOK-HEADING-01: where the book prints only a topic's heading and runs straight into its first subtopic (Chemistry
// XI 14.4 into 14.4.1), the reader goes on with that subtopic under its own heading instead of an empty page.

type Reading = {
  number: string | null;
  availability: string;
  next_topic_id: string | null;
  lesson: { body: { [key: string]: unknown } | null } | null;
};

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
