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
