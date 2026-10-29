// BOOK-BOX-01 (owner, 2026-10-29): the book's printed boxes keep the book's look. Each kind has its own coloured header
// (as printed: Thumb Rule blue, Do You Know green, Quick Quiz / Brain Teaser purple …), and a short box sits at the side
// of the text on wide screens, as in the book's margin. Identical in apps/web and apps/mobile (a host test compares them).

export type BookBoxKind = "rule" | "know" | "info" | "ponder" | "keep" | "activity";

const KINDS: [BookBoxKind, RegExp][] = [
  ["rule", /thumb rule|remember\b/i],
  ["keep", /keep in mind|yaad rakh/i],
  ["know", /d(o|id) you know|kya aap jante/i],
  ["ponder", /ponder|brain teaser|quick quiz|think over|critical thinking|ghaur/i],
  ["activity", /activity/i],
];

/** The kind of a printed box from its title; any other printed box is an information box. */
export function bookBoxKind(title: string): BookBoxKind {
  return KINDS.find(([, re]) => re.test(title))?.[0] ?? "info";
}

/** A box short enough to sit at the side of the text (about the book's margin column) on a wide screen. */
export function sideBox(text: string): boolean {
  return text.length <= 420;
}
