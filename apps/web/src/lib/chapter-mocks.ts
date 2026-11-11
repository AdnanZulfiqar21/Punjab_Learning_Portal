// CHAPTER-MOCK-01 (owner, 2026-11-10): chapter-wise mock tests in the Board paper pattern, made from the chapter's own
// practice questions (Chapter practice: MCQs, short and long questions). The owner checks one test before more are
// added, so only the tests listed in OPEN are offered.

/** One Board paper pattern (Intermediate, new course). */
export type MockPattern = {
  /** Objective part: number of MCQs (1 mark each) and minutes. */
  mcqs: number;
  objectiveMinutes: number;
  /** Section-I: question number, parts asked, parts to attempt (2 marks each). */
  short: { no: number; asked: number; attempt: number }[];
  /** Section-II: questions asked, questions to attempt, marks of the (a) and (b) parts. */
  long: { asked: number; attempt: number; parts: [number, number] };
  subjectiveMinutes: number;
};

// Physics Part-I and Part-II papers (owner's Board papers, 2025-2026): 17 MCQs in 20 minutes; Section-I 8 of 12, 8 of 12,
// 6 of 9; Section-II 3 of 5, each (a) 5 + (b) 3 marks; 2:40 hours; 17 + 68 = 85 marks.
const PHYSICS: MockPattern = {
  mcqs: 17,
  objectiveMinutes: 20,
  short: [
    { no: 2, asked: 12, attempt: 8 },
    { no: 3, asked: 12, attempt: 8 },
    { no: 4, asked: 9, attempt: 6 },
  ],
  long: { asked: 5, attempt: 3, parts: [5, 3] },
  subjectiveMinutes: 160,
};

export const PATTERNS: Record<string, MockPattern> = { physics: PHYSICS };

/** Tests offered now, by "subject-grade" and chapter (owner: Physics 11 chapter 1 first, for checking; all three tests
 * from 2026-11-11). */
export const OPEN: Record<string, Record<number, number[]>> = {
  "physics-11": { 1: [1, 2, 3] },
};

export function openTests(
  subject: string,
  grade: number,
  chapter: number,
): number[] {
  return OPEN[`${subject}-${grade}`]?.[chapter] ?? [];
}

/** How many mock tests a chapter will have; test n uses every 3rd question from n, so the tests don't repeat questions. */
export const TESTS_PER_CHAPTER = 3;

export type Checkpoint = {
  type: string;
  prompt?: string;
  options?: { id: string; text: string }[];
  answer_id?: string;
  explanation?: string;
  answer_table?: { header: string[]; rows: string[][] } | null;
  steps?: string[] | null;
  final_answer?: string | null;
};

export type PaperQuestion = {
  q: string;
  marks: number;
  options?: string[];
  key?: number;
  answer: {
    text?: string;
    table?: { header: string[]; rows: string[][] };
    steps?: string[];
    final?: string;
  };
};

export type Paper = {
  pattern: MockPattern;
  mcqs: PaperQuestion[];
  short: { no: number; attempt: number; parts: PaperQuestion[] }[];
  long: { a: PaperQuestion; b: PaperQuestion }[];
};

const clean = (p: string) =>
  p
    .replace(/^\d+\s+/, "")
    .replace(/\s*\((\d+) marks?\)\s*$/, "")
    .trim();
const marksOf = (p: string) => Number(/\((\d+) marks?\)\s*$/.exec(p)?.[1] ?? 0);

function question(b: Checkpoint, marks: number): PaperQuestion {
  const opts = b.options ?? [];
  return {
    q: clean(b.prompt ?? ""),
    marks,
    ...(opts.length
      ? {
          options: opts.map((o) => o.text),
          key: opts.findIndex((o) => o.id === b.answer_id),
        }
      : {}),
    answer: {
      text: b.explanation || undefined,
      table: b.answer_table ?? undefined,
      steps: b.steps ?? undefined,
      final: b.final_answer ?? undefined,
    },
  };
}

/** `count` items for each of the chapter's tests (indexes into the bank, book order kept). Test n first takes every
 * 3rd item from n-1, so each test covers the whole chapter, evenly thinned when there are more than it needs. A
 * chapter too short for three full tests tops a test up with the items the earlier tests used least (then the earliest),
 * so the tests repeat as few questions as possible. Test 1 is built first and does not depend on the later ones. */
function allocate(size: number, count: number): number[][] {
  const used = new Array<number>(size).fill(0);
  const tests: number[][] = [];
  for (let n = 1; n <= TESTS_PER_CHAPTER; n++) {
    const mine = Array.from({ length: size }, (_, i) => i).filter(
      (i) => i % TESTS_PER_CHAPTER === n - 1,
    );
    let chosen: number[];
    if (mine.length >= count) {
      chosen = Array.from(
        { length: count },
        (_, j) => mine[Math.floor((j * mine.length) / count)],
      );
    } else {
      const extra = Array.from({ length: size }, (_, i) => i)
        .filter((i) => i % TESTS_PER_CHAPTER !== n - 1)
        .sort((x, y) => used[x] - used[y] || x - y)
        .slice(0, count - mine.length);
      chosen = [...mine, ...extra].sort((x, y) => x - y);
    }
    chosen.forEach((i) => used[i]++);
    tests.push(chosen);
  }
  return tests;
}

function pick<T>(bank: T[], n: number, count: number): T[] {
  return allocate(bank.length, count)[n - 1].map((i) => bank[i]);
}

/** A small seeded shuffle, so the objective part is mixed (as on the Board paper) but the same every time. */
function shuffled<T>(xs: T[], seed: number): T[] {
  let s = seed >>> 0;
  const rnd = () => (s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32;
  const out = [...xs];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

const checkpoints = (blocks: { type: string }[]) =>
  blocks.filter((b): b is Checkpoint => b.type === "checkpoint");

/** Build mock test n of a chapter from its three practice sets (English lesson blocks). */
export function buildPaper(
  pattern: MockPattern,
  chapter: number,
  n: number,
  sets: {
    mcq: { type: string }[];
    short: { type: string }[];
    long: { type: string }[];
  },
): Paper {
  const mcqs = shuffled(
    pick(checkpoints(sets.mcq), n, pattern.mcqs),
    chapter * 100 + n,
  ).map((b) => question(b, 1));
  const shortCount = pattern.short.reduce((a, s) => a + s.asked, 0);
  const shorts = pick(checkpoints(sets.short), n, shortCount).map((b) =>
    question(b, 2),
  );
  let at = 0;
  const short = pattern.short.map((s) => {
    const parts = shorts.slice(at, at + s.asked);
    at += s.asked;
    return { no: s.no, attempt: s.attempt, parts };
  });
  const longs = checkpoints(sets.long);
  const [ma, mb] = pattern.long.parts;
  // The long set is written as (a) theory + (b) numerical pairs on the same section; keep each pair together.
  const pairs: { a: Checkpoint; b: Checkpoint }[] = [];
  for (let i = 0; i + 1 < longs.length; i++) {
    if (
      marksOf(longs[i].prompt ?? "") === ma &&
      marksOf(longs[i + 1].prompt ?? "") === mb
    )
      pairs.push({ a: longs[i], b: longs[++i] });
  }
  const long = pick(pairs, n, pattern.long.asked).map((p) => ({
    a: question(p.a, ma),
    b: question(p.b, mb),
  }));
  return { pattern, mcqs, short, long };
}
