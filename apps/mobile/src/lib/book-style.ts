// BOOK-STYLE-01: a premium reading style for one book at a time (owner, 2026-10-28: Class 11 Computer Science first).
// The printed words never change; only how they are drawn: a list item that starts with a term and a colon
// ("Interviews and Surveys: Asking questions …") shows the term bold in the subject colour, and a short lead-in line
// ("Key activities in this phase include:", "Example:") is set as a small heading. Identical in apps/web and
// apps/mobile (a host test compares the two files).

/** The books drawn in the premium style, as subject key and class. */
const STYLED = new Set(["computer_science:11"]);

export function premiumBook(subject: string | null | undefined, grade: number | null | undefined): boolean {
  return STYLED.has(`${subject ?? ""}:${grade ?? ""}`);
}

/** "Term: the rest" split at its colon, when the start is a short term (at most six words, no sentence inside). A book
 * error that would be cut in two by the split keeps the item whole, so its red mark stays complete. */
export function leadTerm(text: string, marks: string[] = []): [string, string] | null {
  const m = /^([A-Z][^:.!?\n]{0,58}?):[ \t]+(\S[\s\S]*)$/.exec(text);
  if (!m) return null;
  const [, term, rest] = m;
  if (term.trim().split(/\s+/).length > 6 || (term.match(/\(/g) ?? []).length !== (term.match(/\)/g) ?? []).length) return null;
  if (marks.some((k) => text.includes(k) && !term.includes(k) && !rest.includes(k))) return null;
  return [term, rest];
}

/** A short line that only introduces what follows ("Example:", "Key activities in this phase include:"). */
export function leadIn(text: string): boolean {
  const t = text.trim();
  return t.length <= 80 && /^[A-Z][^.!?\n]*:$/.test(t);
}
