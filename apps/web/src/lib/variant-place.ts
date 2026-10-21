// Where to land after a language switch (READER-PLACE-01). Since EN-BOOK-ONLY-01 the English lesson carries only the
// book and the Roman Urdu lesson adds our explanations, so the two variants no longer share one block structure. Each
// block gets a short signature: its kind, the archived figure it shows, and the technical words and numbers in it
// (these stay in English inside Roman Urdu text). The two lists are aligned, and the block the reader was on maps to
// its partner, or to the partner of the nearest earlier block that has one. Kept identical on web and mobile.

export type PlaceBlock = { type: string } & Record<string, unknown>;

const MAX_WORDS = 16;
const SKIP_KEYS = new Set(["type", "tone", "mode", "level", "ordered", "alt", "long_description", "caption", "labels", "fallback"]);

function collect(value: unknown, out: string[]): void {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach((v) => collect(v, out));
  else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) if (!SKIP_KEYS.has(k) && !k.includes("asset") && !k.startsWith("$")) collect(v, out);
  }
}

/** "kind|figure|word word ..." for one block. */
export function placeSignature(b: PlaceBlock): string {
  const items = Array.isArray(b.items) ? b.items.map((x) => String(x).trim()) : [];
  // The book's own questions are a numbered list in English and separate self-checks in Roman Urdu.
  const questions = b.type === "checkpoint" || (b.type === "list" && b.ordered === true && items.filter((x) => x.endsWith("?")).length * 2 >= items.length);
  const kind = questions
    ? "question"
    : b.type === "heading"
      ? `heading${String(b.level ?? "")}`
      : b.type === "callout"
        ? `callout-${String(b.tone ?? "")}`
        : b.type;
  const figure =
    b.type === "diagram" ? String(b.asset_version_id ?? b.$asset ?? "") : b.type === "model3d" ? String(b.poster_asset_version_id ?? b.$poster ?? b.model ?? "") : "";
  const text: string[] = [];
  collect(b, text);
  const words = text.join(" ").toLowerCase().match(/[a-z]{5,}|[a-z]*\d[a-z0-9.+-]*/g) ?? [];
  return `${kind}|${figure}|${[...new Set(words)].slice(0, MAX_WORDS).join(" ")}`;
}

function parse(sig: string): { kind: string; figure: string; words: Set<string> } {
  const [kind = "", figure = "", words = ""] = sig.split("|");
  return { kind, figure, words: new Set(words.split(" ").filter(Boolean)) };
}

/** How well two blocks correspond (0: they cannot be partners). */
export function placeScore(a: string, b: string): number {
  const x = parse(a);
  const y = parse(b);
  if (x.figure || y.figure) return x.figure && x.figure === y.figure ? 10 : 0; // a figure only matches the same figure
  let shared = 0;
  x.words.forEach((w) => {
    if (y.words.has(w)) shared += 1;
  });
  const overlap = shared / Math.max(1, Math.min(x.words.size, y.words.size));
  if (x.kind === y.kind) return 1 + 3 * overlap;
  return overlap >= 0.3 ? 2 * overlap : 0; // e.g. the book's questions as a list in English, as self-checks in Roman Urdu
}

/** Partners between two block lists: the order-keeping pairing with the highest total score. */
export function alignPlaces(from: string[], to: string[]): Map<number, number> {
  const n = from.length;
  const m = to.length;
  const best: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  const score: number[][] = Array.from({ length: n }, (_, i) => to.map((t) => placeScore(from[i], t)));
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      const s = score[i - 1][j - 1];
      best[i][j] = Math.max(best[i - 1][j], best[i][j - 1], s > 0 ? best[i - 1][j - 1] + s : 0);
    }
  }
  const pairs = new Map<number, number>();
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    const s = score[i - 1][j - 1];
    if (s > 0 && best[i][j] === best[i - 1][j - 1] + s) {
      pairs.set(i - 1, j - 1);
      i -= 1;
      j -= 1;
    } else if (best[i][j] === best[i - 1][j]) i -= 1;
    else j -= 1;
  }
  return pairs;
}

/** The block to show in the other variant for the block the reader was on. */
export function mapPlace(from: string[], to: string[], index: number): number {
  if (to.length === 0) return 0;
  const pairs = alignPlaces(from, to);
  const taken = new Set(pairs.values());
  for (let i = Math.min(index, from.length - 1); i >= 0; i--) {
    let j = pairs.get(i);
    if (j === undefined) continue;
    // One block can stand for several (a list of the book's questions for our separate self-checks): land on the first.
    while (j > 0 && !taken.has(j - 1) && placeScore(from[i], to[j - 1]) > 0) j -= 1;
    return j;
  }
  return 0;
}
