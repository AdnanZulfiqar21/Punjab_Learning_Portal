// BOOK-MISTAKES-01 (owner, 2026-11-12): Practice → Book mistakes lists the errors printed in a textbook, by chapter and
// topic, each with its correction. The owner reviews one book first (Class 11 Physics); the others open once they
// approve it. A book not listed here shows a short "being checked" notice instead of its list.
export const BOOK_MISTAKES_READY: readonly (readonly [number, string])[] = [[11, "physics"]];

export const bookMistakesReady = (grade: number, subject: string) =>
  BOOK_MISTAKES_READY.some(([g, s]) => g === grade && s === subject);

/** "1 mistake", "3 mistakes". */
export const mistakeCount = (n: number) => `${n} ${n === 1 ? "mistake" : "mistakes"}`;

/** Where a topic is read: the end-of-chapter exercise opens in Practice, every other topic in Learn. */
export const topicHref = (t: { topic_id: string; practice_only: boolean }) =>
  t.practice_only ? `/practice/exercises/${t.topic_id}` : `/learn/topic/${t.topic_id}`;
