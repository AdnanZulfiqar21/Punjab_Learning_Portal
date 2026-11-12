// BOOK-MOCK-01 (owner, 2026-11-13): Practice → Book Mock Test has two tabs, "Full book mock test" and "Half book mock
// test". A half book is the book split in two (e.g. chapters 1-6 and 7-12). Owner, same day: a third kind, the book in
// four parts ("12 chapter ko 4 hisso ma ... 3 3"): "Quarter book mock test" (e.g. chapters 1-3, 4-6, 7-9, 10-12). Each test is a full Board-pattern paper put
// together from the chapters' own practice questions (Chapter practice), as many tests as the questions allow without
// repeating a question. Owner, same day: "seedhy seedhy mt banana, shuffle kr ka tricky sa banana": the questions are
// drawn at random from all the chapters, mixed together, and the MCQ options are shuffled. Every test is still the same
// on every visit (seeded).
import {
  checkpoints,
  longUnits,
  question,
  shuffled,
  type Checkpoint,
  type MockPattern,
  type Paper,
  type PaperQuestion,
} from "./chapter-mocks";

/** A stretch of the book with its own numbered tests. */
export type BookPart = { key: string; from: number; to: number; tests: number };

/** What a book offers: the full book, its two halves and its four quarters. */
export type BookMocks = { full: BookPart; halves: BookPart[]; quarters: BookPart[] };

/** The three kinds of book mock test (the page's tabs). */
export type BookMockKind = "full" | "half" | "quarter";

/** A kind's parts: the full book alone, the halves or the quarters. */
export const partsOf = (b: BookMocks, kind: BookMockKind): BookPart[] =>
  kind === "full" ? [b.full] : kind === "half" ? b.halves : b.quarters;

const part = (from: number, to: number, tests: number): BookPart => ({ key: `${from}-${to}`, from, to, tests });

/** Books with book mock tests, by "subject-grade". A half book is the first and second half of the book's chapters, a
 * quarter one of four parts (a count that does not divide evenly gives the first parts one more chapter). `tests` is how many Board papers the practice questions fill without
 * repeating a question: the smallest of MCQs / paper MCQs, short questions / paper short questions and Section-II
 * questions / 5 (counted 2026-11-13 from the practice sets; e.g. Physics 11 chapters 1-6 have 811 MCQs, 434 short
 * questions and 76 long pairs: 13 papers of 17, 33 and 5). Owner: Physics 11 first, then every book the same day. */
export const BOOK_OPEN: Record<string, BookMocks> = {
  "physics-11": { full: part(1, 12, 26), halves: [part(1, 6, 13), part(7, 12, 13)], quarters: [part(1, 3, 6), part(4, 6, 6), part(7, 9, 7), part(10, 12, 5)] },
  "chemistry-11": { full: part(1, 16, 34), halves: [part(1, 8, 18), part(9, 16, 16)], quarters: [part(1, 4, 9), part(5, 8, 9), part(9, 12, 9), part(13, 16, 6)] },
  "biology-11": { full: part(1, 12, 20), halves: [part(1, 6, 11), part(7, 12, 9)], quarters: [part(1, 3, 6), part(4, 6, 5), part(7, 9, 4), part(10, 12, 4)] },
  "computer_science-11": { full: part(1, 9, 21), halves: [part(1, 5, 13), part(6, 9, 7)], quarters: [part(1, 3, 8), part(4, 5, 5), part(6, 7, 4), part(8, 9, 3)] },
  "mathematics-11": { full: part(1, 14, 19), halves: [part(1, 7, 9), part(8, 14, 9)], quarters: [part(1, 4, 5), part(5, 8, 5), part(9, 11, 3), part(12, 14, 4)] },
  "physics-12": { full: part(13, 21, 20), halves: [part(13, 17, 11), part(18, 21, 8)], quarters: [part(13, 15, 6), part(16, 17, 5), part(18, 19, 4), part(20, 21, 4)] },
  "chemistry-12": { full: part(17, 33, 32), halves: [part(17, 25, 17), part(26, 33, 15)], quarters: [part(17, 21, 10), part(22, 25, 7), part(26, 29, 7), part(30, 33, 8)] },
  "biology-12": { full: part(13, 25, 22), halves: [part(13, 19, 12), part(20, 25, 8)], quarters: [part(13, 16, 7), part(17, 19, 5), part(20, 22, 5), part(23, 25, 3)] },
  "computer_science-12": { full: part(1, 9, 19), halves: [part(1, 5, 9), part(6, 9, 9)], quarters: [part(1, 3, 6), part(4, 5, 3), part(6, 7, 4), part(8, 9, 4)] },
  "mathematics-12": { full: part(1, 11, 16), halves: [part(1, 6, 10), part(7, 11, 6)], quarters: [part(1, 3, 6), part(4, 6, 4), part(7, 9, 3), part(10, 11, 2)] },
};

export const bookMocks = (subject: string, grade: number): BookMocks | undefined => BOOK_OPEN[`${subject}-${grade}`];

/** The full book, a half or a quarter, by its key ("1-12", "1-6", "1-3"). */
export function bookPart(
  subject: string,
  grade: number,
  key: string,
): { part: BookPart; kind: BookMockKind } | undefined {
  const b = bookMocks(subject, grade);
  if (!b) return undefined;
  for (const kind of ["full", "half", "quarter"] as const) {
    const part = partsOf(b, kind).find((x) => x.key === key);
    if (part) return { part, kind };
  }
  return undefined;
}

/** "Chapters 1–6". */
export const partLabel = (p: BookPart, label = "Chapter") => `${label}s ${p.from}–${p.to}`;

/**
 * `count` items for test n of `tests`, taken from every chapter's bank in proportion to its size. Each chapter's bank is
 * walked in a fixed random order, so the tests share no item until a bank runs out. Which chapters get the odd extra
 * item rotates from test to test (the slots are dealt to the chapter furthest behind its share), so no chapter is
 * always left out of a small section such as the five long questions.
 */
function deal<T>(banks: T[][], tests: number, n: number, count: number, seed: number): T[] {
  const total = banks.reduce((a, b) => a + b.length, 0);
  if (!total) return [];
  const orders = banks.map((b, c) => shuffled(b, seed * 31 + c + 1));
  const given = banks.map(() => 0);
  let out: T[] = [];
  for (let t = 1; t <= Math.min(n, tests); t++) {
    out = [];
    for (let k = 0; k < count; k++) {
      const slot = (t - 1) * count + k + 1;
      let best = -1;
      let gap = -Infinity;
      banks.forEach((b, c) => {
        const d = (slot * b.length) / total - given[c];
        if (b.length && d > gap) [best, gap] = [c, d];
      });
      const order = orders[best];
      out.push(order[given[best] % order.length]);
      given[best]++;
    }
  }
  return out;
}

/** Options that point at other options ("all of the above", "both (a) and (b)") keep their order. */
const FIXED = /above|below|both|neither|none of|all of|\([a-e]\)|\b[a-e] and [a-e]\b/i;

/** Shuffle an MCQ's options (seeded) and move the key with them, unless the options or the explanation name a letter. */
function mixOptions(q: PaperQuestion, b: Checkpoint, seed: number): PaperQuestion {
  if (!q.options || q.key === undefined || q.key < 0) return q;
  if (q.options.some((o) => FIXED.test(o)) || /\b(option|choice)\s*\(?[a-e]\b|\([a-e]\)/i.test(b.explanation ?? ""))
    return q;
  const order = shuffled(
    q.options.map((_, i) => i),
    seed,
  );
  return { ...q, options: order.map((i) => q.options![i]), key: order.indexOf(q.key) };
}

/** The same question is sometimes written twice in the practice sets: in two chapters ("State Avogadro's law." in
 * Chemistry 11 chapters 4 and 5), or as a short and a long question of one chapter. A book mock test uses it once:
 * Section-II keeps it, then the short questions, then the MCQs, each from the first chapter that has it. */
function unique<T>(banks: T[][], texts: (x: T) => string[], seen: Set<string>): T[][] {
  const key = (t: string) => t.replace(/\s+/g, " ").trim().toLowerCase();
  return banks.map((b) =>
    b.filter((x) => {
      const ks = texts(x).map(key);
      if (ks.some((k) => seen.has(k))) return false;
      ks.forEach((k) => seen.add(k));
      return true;
    }),
  );
}

/** Build book mock test n of a part from its chapters' practice sets (English lesson blocks), in chapter order. */
export function buildBookPaper(
  pattern: MockPattern,
  part: BookPart,
  n: number,
  chapters: { mcq: { type: string }[]; short: { type: string }[]; long: { type: string }[] }[],
): Paper {
  const seed = part.from * 1000 + part.to * 10;
  const prompt = (b: Checkpoint) => question(b, 0).q;
  const seen = new Set<string>();
  const longBanks = unique(
    chapters.map((c) => longUnits(pattern, checkpoints(c.long))),
    (u) => (u.b ? [prompt(u.a), prompt(u.b)] : [prompt(u.a)]),
    seen,
  );
  const shortBanks = unique(
    chapters.map((c) => checkpoints(c.short)),
    (b) => [prompt(b)],
    seen,
  );
  const mcqBanks = unique(
    chapters.map((c) => checkpoints(c.mcq)),
    (b) => [prompt(b)],
    seen,
  );
  const mcqs = shuffled(deal(mcqBanks, part.tests, n, pattern.mcqs, seed + 1), seed + n).map((b, i) =>
    mixOptions(question(b, 1), b, seed * 7 + n * 101 + i),
  );
  const shortCount = pattern.short.reduce((a, s) => a + s.asked, 0);
  const shorts = shuffled(deal(shortBanks, part.tests, n, shortCount, seed + 2), seed + 50 + n).map((b) =>
    question(b, 2),
  );
  let at = 0;
  const short = pattern.short.map((s) => {
    const parts = shorts.slice(at, at + s.asked);
    at += s.asked;
    return { no: s.no, attempt: s.attempt, parts };
  });
  const [ma, mb] = pattern.long.parts;
  const long = shuffled(deal(longBanks, part.tests, n, pattern.long.asked, seed + 3), seed + 90 + n).map((u) => ({
    a: question(u.a, ma),
    ...(u.b && mb !== undefined ? { b: question(u.b, mb) } : {}),
  }));
  return { pattern, mcqs, short, long };
}
