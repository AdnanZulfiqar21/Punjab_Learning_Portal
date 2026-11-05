// Book exercises (BOOK-EXERCISES-01): each chapter's end-of-chapter exercise is solved in Practice, in English or
// Roman Urdu, and never listed in Learn. The API marks it (`kind: "exercise"`, from the catalogue key `…/u-exercise`).
// BOOK-PAPERS-01: so are the Board papers at the end of a book (`kind: "paper"`, `…/u-paper-pattern`, `…/u-model-paper`).
// Pure rules for host tests; the same words as the web (apps/web/src/lib/exercises.ts).

/** Whether a topic is opened from Practice only (a chapter's exercise or a Board paper); Learn never leads into it. */
export function practiceOnly(kind: string | undefined): boolean {
  return kind !== undefined && kind !== "topic";
}

/** A chapter's topics as Learn lists them: without the end-of-chapter exercise or the Board papers. */
export function learnTopics<T extends { kind?: string }>(topics: readonly T[]): T[] {
  return topics.filter((t) => !practiceOnly(t.kind));
}

/** "Chapter 2 · Exercise" */
export function exerciseTitle(chapterLabel: string, chapterNumber: number): string {
  return `${chapterLabel} ${chapterNumber} · Exercise`;
}

/** A Practice screen's title: a Board paper's own ("Model Paper", "Paper Pattern"), else "Chapter 2 · Exercise". */
export function practiceTitle(reading: { kind?: string; title: string; chapter_number: number }): string {
  return reading.kind === "paper" ? reading.title : exerciseTitle("Chapter", reading.chapter_number);
}

/** The self-check button's words on an exercise, in the lesson's own language. */
export function revealLabel(language: string): string {
  return language === "roman_ur" ? "Answer dekhein" : "Show answer";
}

/** Whether a chapter's exercise can be opened, as Practice lists it. */
export function exerciseStatus(availability: string, languages: readonly string[]): { label: string; open: boolean } {
  const names = languages.map((l) => (l === "roman_ur" ? "Roman Urdu" : l === "ur" ? "Urdu" : "English")).join(" · ");
  if (availability === "published") return { label: names || "Ready", open: true };
  if (availability === "private_preview") return { label: `Draft preview${names ? ` · ${names}` : ""}`, open: true };
  return { label: "Not ready yet", open: false };
}
