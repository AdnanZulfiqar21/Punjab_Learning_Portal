// BOOK-MOCK-01 (owner, 2026-11-13): Practice → Book Mock Test has two tabs, "Full book mock test" and "Half book mock
// test". A half book is the book split in two (e.g. chapters 1-6 and 7-12). Each test is a full Board-pattern paper put
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

/** What a book offers: the full book, and the two halves. */
export type BookMocks = { full: BookPart; halves: BookPart[] };

const part = (from: number, to: number, tests: number): BookPart => ({ key: `${from}-${to}`, from, to, tests });

/** Books with book mock tests, by "subject-grade". `tests` is how many Board papers the practice questions fill without
 * repeating a question: the short questions decide it (Physics 11: chapters 1-6 have 434 short questions, 13 papers of
 * 33; chapters 7-12 have 431, 13 papers; the whole book 865, 26 papers). Owner: Physics 11 first, for checking. */
export const BOOK_OPEN: Record<string, BookMocks> = {
  "physics-11": { full: part(1, 12, 26), halves: [part(1, 6, 13), part(7, 12, 13)] },
};

export const bookMocks = (subject: string, grade: number): BookMocks | undefined => BOOK_OPEN[`${subject}-${grade}`];

/** The full book or a half, by its key ("1-12", "1-6"). */
export function bookPart(subject: string, grade: number, key: string): { part: BookPart; half: boolean } | undefined {
  const b = bookMocks(subject, grade);
  if (!b) return undefined;
  if (b.full.key === key) return { part: b.full, half: false };
  const h = b.halves.find((x) => x.key === key);
  return h ? { part: h, half: true } : undefined;
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

/** Build book mock test n of a part from its chapters' practice sets (English lesson blocks), in chapter order. */
export function buildBookPaper(
  pattern: MockPattern,
  part: BookPart,
  n: number,
  chapters: { mcq: { type: string }[]; short: { type: string }[]; long: { type: string }[] }[],
): Paper {
  const seed = part.from * 1000 + part.to * 10;
  const mcqBanks = chapters.map((c) => checkpoints(c.mcq));
  const mcqs = shuffled(deal(mcqBanks, part.tests, n, pattern.mcqs, seed + 1), seed + n).map((b, i) =>
    mixOptions(question(b, 1), b, seed * 7 + n * 101 + i),
  );
  const shortCount = pattern.short.reduce((a, s) => a + s.asked, 0);
  const shorts = shuffled(
    deal(
      chapters.map((c) => checkpoints(c.short)),
      part.tests,
      n,
      shortCount,
      seed + 2,
    ),
    seed + 50 + n,
  ).map((b) => question(b, 2));
  let at = 0;
  const short = pattern.short.map((s) => {
    const parts = shorts.slice(at, at + s.asked);
    at += s.asked;
    return { no: s.no, attempt: s.attempt, parts };
  });
  const [ma, mb] = pattern.long.parts;
  const long = shuffled(
    deal(
      chapters.map((c) => longUnits(pattern, checkpoints(c.long))),
      part.tests,
      n,
      pattern.long.asked,
      seed + 3,
    ),
    seed + 90 + n,
  ).map((u) => ({ a: question(u.a, ma), ...(u.b && mb !== undefined ? { b: question(u.b, mb) } : {}) }));
  return { pattern, mcqs, short, long };
}
