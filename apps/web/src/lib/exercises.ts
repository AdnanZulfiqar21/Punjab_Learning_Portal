// Book exercises (BOOK-EXERCISES-01): each chapter's end-of-chapter exercise is solved in Practice, in English or
// Roman Urdu, and never listed in Learn. Same words as the app (apps/mobile/src/lib/exercises.ts).

/** "Chapter 2 · Exercise" */
export function exerciseTitle(chapterLabel: string, chapterNumber: number): string {
  return `${chapterLabel} ${chapterNumber} · Exercise`;
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
