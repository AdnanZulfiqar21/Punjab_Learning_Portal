// DESIGN-01 (Practice pages): the class and subject pill filters shared by Practice, Book exercises and Written practice.

/**
 * The subjects the portal teaches, in the given order. Mathematics books are indexed but not taught (owner,
 * 2026-10-19), so no Practice filter offers them.
 */
export function taughtSubjects(subjects: readonly (readonly [string, string])[]): [string, string][] {
  return subjects.filter(([code]) => code !== "mathematics").map(([code, name]) => [code, name]);
}

/** A Practice page for one class and subject ("/practice?grade=11&subject=biology"). */
export function filterHref(path: string, grade: number, subject: string): string {
  return `${path}?grade=${grade}&subject=${encodeURIComponent(subject)}`;
}
