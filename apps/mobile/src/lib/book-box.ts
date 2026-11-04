// BOOK-BOX-01 (owner, 2026-10-29): the book's printed boxes keep the book's look. Each kind has its own coloured header,
// in a premium jewel-tone palette so boxes of different kinds never look alike (owner: "sary boxes ka colors same mt
// rakha ... premium colours"), and a short box sits at the side of the text on wide screens, as in the book's margin.
// Identical in apps/web and apps/mobile (a host test compares them).

export const BOOK_BOX_KINDS = [
  "rule",
  "know",
  "info",
  "interesting",
  "tidbit",
  "ponder",
  "teaser",
  "quiz",
  "check",
  "keep",
  "activity",
  "fact",
] as const;
export type BookBoxKind = (typeof BOOK_BOX_KINDS)[number];

// The first match wins, so the more specific titles come first ("Interesting Application" is a fact, not information).
const KINDS: [BookBoxKind, RegExp][] = [
  ["rule", /thumb rule|remember\b/i],
  ["keep", /keep in mind|yaad rakh/i],
  ["know", /d(o|id) you know|kya aap jante/i],
  ["fact", /scientific fact|interesting application/i],
  ["interesting", /interesting|fascinating|dilchasp/i],
  ["tidbit", /tid-?bits?/i],
  ["teaser", /brain teaser|dimagh/i],
  ["check", /quick check|self[- ]assessment/i],
  ["quiz", /quick quiz|quiz/i],
  ["ponder", /ponder|think over|critical thinking|ghaur/i],
  ["activity", /activity/i],
];

/** The kind of a printed box from its title; any other printed box ("For Your Information" …) is an information box. */
export function bookBoxKind(title: string): BookBoxKind {
  return KINDS.find(([, re]) => re.test(title))?.[0] ?? "info";
}

/** A box short enough to sit at the side of the text (about the book's margin column) on a wide screen. */
export function sideBox(text: string): boolean {
  return text.length <= 420;
}

type BlockLike = { type?: unknown; tone?: unknown; title?: unknown; [field: string]: unknown };

/** A printed box: a titled note callout (our tips, corrections and untitled notes are not the book's boxes). */
export function isBookBox(b: BlockLike | undefined): boolean {
  const title = typeof b?.title === "string" ? b.title.trim() : "";
  return b?.type === "callout" && (b.tone ?? "note") === "note" && title !== "" && title.toLowerCase() !== "note";
}

/** A margin note the book prints without a title (an untitled note callout): drawn like a printed box but with no header,
 * and at the side of the text when it is short, as in the book's margin (owner, 2026-11-02). */
export function isMarginNote(b: BlockLike | undefined): boolean {
  const title = typeof b?.title === "string" ? b.title.trim() : "";
  return b?.type === "callout" && (b.tone ?? "note") === "note" && title === "";
}

/** A box the book prints across the full page width (BOOK-LAYOUT-02, owner 2026-11-04): it never moves to the side
 * of the text or into a row of boxes, however short it is. */
export function isWide(b: BlockLike | undefined): boolean {
  return b?.type === "callout" && b.wide === true;
}

/** A printed box that may share a row with the boxes next to it (not one printed across the page). */
export function isRowBox(b: BlockLike | undefined): boolean {
  return isBookBox(b) && !isWide(b);
}

/** At the first box of a run of printed boxes next to each other, the run's length; 0 anywhere else. Boxes in a run
 * sit side by side on a wide screen instead of stacking in the margin (owner, 2026-10-29). */
export function boxRun(blocks: readonly BlockLike[], i: number): number {
  if (!isRowBox(blocks[i]) || isRowBox(blocks[i - 1])) return 0;
  let n = 1;
  while (isRowBox(blocks[i + n])) n++;
  return n;
}

const FLOWS = new Set(["paragraph", "list", "heading"]);

/** A figure the book prints beside the text rather than across the page (BOOK-LAYOUT-01, owner 2026-11-03). */
export function isSideFigure(b: BlockLike | undefined): boolean {
  return b?.type === "diagram" && b.side === true;
}

/** A short printed box or margin note that the book does not print across the page: it sits at the side of the text. */
export function isSideBox(b: BlockLike | undefined): boolean {
  return (isBookBox(b) || isMarginNote(b)) && !isWide(b) && typeof b?.text === "string" && sideBox(b.text);
}

/** A short printed box, a margin note or a side figure: it floats at the side of the text on a wide screen. */
function floats(b: BlockLike | undefined): boolean {
  return isSideBox(b) || isSideFigure(b);
}

/** The order to draw a lesson's blocks in. Side boxes that come right after a paragraph or list are drawn just before
 * it, so that the paragraph (and any text after the boxes) flows beside them, as the book prints a margin box beside the
 * text it belongs to; otherwise the boxes would float below the paragraph and often leave an empty column on the left
 * (owner, 2026-11-02). Boxes drawn side by side in one row are not moved. */
export function sideOrder(blocks: readonly BlockLike[]): number[] {
  const order: number[] = [];
  let i = 0;
  while (i < blocks.length) {
    let n = 0;
    while (floats(blocks[i + 1 + n])) n++;
    const text = blocks[i]?.type === "paragraph" || blocks[i]?.type === "list";
    if (text && n > 0 && boxRow(blocks, i + 1) === 0) {
      for (let k = 1; k <= n; k++) order.push(i + k);
      order.push(i);
      i += n + 1;
    } else {
      order.push(i);
      i++;
    }
  }
  return order;
}

/** A run of printed boxes is drawn side by side in one row only when no text would flow beside it on the left (the
 * block after the run is not a paragraph, list or heading, or the lesson ends); otherwise the boxes keep to the margin
 * with the text beside them (owner, 2026-10-29). Returns the run's length for such a row, else 0. */
export function boxRow(blocks: readonly BlockLike[], i: number): number {
  const run = boxRun(blocks, i);
  if (run < 2) return 0;
  const after = blocks[i + run];
  return after && FLOWS.has(String(after.type)) ? 0 : run;
}
