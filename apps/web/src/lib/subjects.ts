// The subjects the portal teaches, in display order. Mathematics was indexed but not taught (owner, 2026-10-19); on
// 2026-11-05 the owner started Mathematics 11 (MATHS-11-01), and on 2026-11-06 Mathematics 12 the same way
// (MATHS-12-01), so both Mathematics books are taught.
export const TAUGHT_SUBJECTS = ["biology", "chemistry", "physics", "computer_science", "mathematics"] as const;

const TAUGHT = new Set<string>(TAUGHT_SUBJECTS);

/** Whether the portal teaches a subject (both classes). */
export function isTaught(subject: string): boolean {
  return TAUGHT.has(subject);
}

/** The books the portal teaches, in their original order. */
export function taughtBooks<T extends { subject: string; grade?: number }>(books: readonly T[]): T[] {
  return books.filter((b) => isTaught(b.subject));
}

/** The class a whole subject tile opens: the learner's own class when the subject has it, else its first class. */
export function tileGrade(grades: readonly number[], preferred: number | undefined): number {
  return preferred !== undefined && grades.includes(preferred) ? preferred : grades[0];
}
