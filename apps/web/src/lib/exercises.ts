// Book exercises (BOOK-EXERCISES-01): each chapter's end-of-chapter exercise is solved in Practice, in English or
// Roman Urdu, and never listed in Learn; so are the Board papers at the end of a book (BOOK-PAPERS-01). Same words as
// the app (apps/mobile/src/lib/exercises.ts).

/** "Chapter 2 · Exercise" */
export function exerciseTitle(chapterLabel: string, chapterNumber: number): string {
  return `${chapterLabel} ${chapterNumber} · Exercise`;
}

/**
 * Whether a topic is opened from Practice only: a chapter's exercise, or (BOOK-PAPERS-01) one of the Board papers at
 * the end of the book. Learn neither lists nor links into it.
 */
export function practiceOnly(kind: string | undefined): boolean {
  return kind !== undefined && kind !== "topic";
}

/** A Practice screen's title: a Board paper's own ("Model Paper", "Paper Pattern"), "Chapter 1 · MCQs", else "Chapter 2 · Exercise". */
export function practiceTitle(reading: { kind?: string; title: string; chapter_number: number }): string {
  if (reading.kind === "paper") return reading.title;
  if (reading.kind === "short") return shortTitle("Chapter", reading.chapter_number);
  return reading.kind === "mcq" ? mcqTitle("Chapter", reading.chapter_number) : exerciseTitle("Chapter", reading.chapter_number);
}

/** PRACTICE-MCQ-01: a chapter's practice MCQs, written from the chapter (not printed in the book): "Chapter 1 · MCQs". */
export function mcqTitle(chapterLabel: string, chapterNumber: number): string {
  return `${chapterLabel} ${chapterNumber} · MCQs`;
}

/** PRACTICE-SHORT-01: a chapter's practice short questions with answers: "Chapter 1 · Short Questions". */
export function shortTitle(chapterLabel: string, chapterNumber: number): string {
  return `${chapterLabel} ${chapterNumber} · Short Questions`;
}

type ChapterItem = { topic_id: string; chapter_number: number; chapter_title: string; availability: string; available_languages: readonly string[] };

/** PRACTICE-MCQ-01: Practice by book, then chapter, as Learn: each chapter with its book exercise and its MCQs (either
 * may be missing), in chapter order. */
export function practiceChapters<E extends ChapterItem>(book: { exercises: readonly E[]; mcq_sets?: readonly E[]; short_sets?: readonly E[] }) {
  const chapters = new Map<number, { number: number; title: string; exercise?: E; mcqs?: E; shorts?: E }>();
  const at = (e: E) => chapters.get(e.chapter_number) ?? chapters.set(e.chapter_number, { number: e.chapter_number, title: e.chapter_title }).get(e.chapter_number)!;
  for (const e of book.exercises) at(e).exercise = e;
  for (const m of book.mcq_sets ?? []) at(m).mcqs = m;
  for (const s of book.short_sets ?? []) at(s).shorts = s;
  return [...chapters.values()].sort((a, b) => a.number - b.number);
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
