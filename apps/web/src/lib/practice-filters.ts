// DESIGN-01 (Practice pages): the class and subject pill filters shared by Practice, Book exercises and Written practice.

/**
 * The subjects whose question practice the portal offers, in the given order. Mathematics has no practice questions
 * (owner, 2026-10-19; Mathematics 11 started 2026-11-05 with book exercises only), so these filters leave it out.
 */
export function taughtSubjects(subjects: readonly (readonly [string, string])[]): [string, string][] {
  return subjects.filter(([code]) => code !== "mathematics").map(([code, name]) => [code, name]);
}

/**
 * The subjects whose book exercises a class has (MATHS-11-01): every practised subject, and Mathematics in Class 11
 * only (owner, 2026-11-05).
 */
export function exerciseSubjects(subjects: readonly (readonly [string, string])[], grade: number): [string, string][] {
  return subjects.filter(([code]) => code !== "mathematics" || grade === 11).map(([code, name]) => [code, name]);
}

/** A Practice page for one class and subject ("/practice?grade=11&subject=biology"). */
export function filterHref(path: string, grade: number, subject: string): string {
  return `${path}?grade=${grade}&subject=${encodeURIComponent(subject)}`;
}
