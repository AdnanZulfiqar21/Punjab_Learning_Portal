// BOOK-MISTAKES-01 (owner, 2026-11-12): Practice → Book mistakes lists the errors printed in a textbook, by chapter and
// topic, each with its correction. Owner, same day: check every box against the printed page before it is shown, and
// add the books chapter by chapter as they are checked (Maths is not listed). A chapter shows here only once each of
// its boxes has been checked against the printed page; the others say "being checked".
export const BOOK_MISTAKES_VERIFIED: Readonly<Record<string, readonly number[]>> = {
  "11/physics": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  "12/physics": [13, 14, 15, 16, 17, 18, 19, 20, 21],
  "11/chemistry": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
  "12/chemistry": [17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],
  "11/biology": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  "12/biology": [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
  "11/computer_science": [1, 2, 3, 4, 5, 6, 7, 8, 9],
};

const verified = (grade: number, subject: string) => BOOK_MISTAKES_VERIFIED[`${grade}/${subject}`] ?? [];

/** Whether any chapter of the book has been checked. */
export const bookMistakesReady = (grade: number, subject: string) => verified(grade, subject).length > 0;

/** Whether this chapter's mistakes have been checked against the printed book. */
export const chapterVerified = (grade: number, subject: string, chapter: number) => verified(grade, subject).includes(chapter);

/** "1 mistake", "3 mistakes". */
export const mistakeCount = (n: number) => `${n} ${n === 1 ? "mistake" : "mistakes"}`;

/** Where a topic is read: the end-of-chapter exercise opens in Practice, every other topic in Learn. */
export const topicHref = (t: { topic_id: string; practice_only: boolean }) =>
  t.practice_only ? `/practice/exercises/${t.topic_id}` : `/learn/topic/${t.topic_id}`;
