// The subjects the portal teaches, in display order. Mathematics books are indexed in the catalogue but not taught
// (owner, 2026-10-19), so learner pages leave them out.
export const TAUGHT_SUBJECTS = ["biology", "chemistry", "physics", "computer_science"] as const;

const TAUGHT = new Set<string>(TAUGHT_SUBJECTS);

/** The books of taught subjects, in their original order. */
export function taughtBooks<T extends { subject: string }>(books: readonly T[]): T[] {
  return books.filter((b) => TAUGHT.has(b.subject));
}
