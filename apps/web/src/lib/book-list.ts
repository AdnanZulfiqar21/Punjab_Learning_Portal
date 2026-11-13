// BOOK-LIST-01: lists and lettered items as the book prints them (owner, 2026-11-13: "book jasi formatting").
// A list block may name the label the book prints before each item ("i-", "(a)", "1-"); each item then shows that
// label in its own column with the item's lines hanging beside it. A paragraph the book starts with such a label
// ("(a) In electroporation, …") is set the same way. The words never change. Identical in apps/web and apps/mobile (a
// host test compares the two files).

/** The labels a list block may name: the first item's label in the book's own style. */
export const LIST_MARKERS = [
  "1.",
  "1-",
  "1)",
  "(1)",
  "a.",
  "a-",
  "a)",
  "(a)",
  "A.",
  "A-",
  "A)",
  "(A)",
  "i.",
  "i-",
  "i)",
  "(i)",
  "I.",
  "I-",
  "I)",
  "(I)",
] as const;

export type ListMarker = (typeof LIST_MARKERS)[number];

const ROMAN: [number, string][] = [
  [1000, "m"],
  [900, "cm"],
  [500, "d"],
  [400, "cd"],
  [100, "c"],
  [90, "xc"],
  [50, "l"],
  [40, "xl"],
  [10, "x"],
  [9, "ix"],
  [5, "v"],
  [4, "iv"],
  [1, "i"],
];

function roman(n: number): string {
  let out = "";
  for (const [v, s] of ROMAN)
    while (n >= v) {
      out += s;
      n -= v;
    }
  return out;
}

function letters(n: number): string {
  let out = "";
  for (let k = n; k > 0; k = Math.floor((k - 1) / 26))
    out = String.fromCharCode(97 + ((k - 1) % 26)) + out;
  return out;
}

export function isListMarker(m: unknown): m is ListMarker {
  return (
    typeof m === "string" && (LIST_MARKERS as readonly string[]).includes(m)
  );
}

/** The label of item n (1-based) in the style of `marker`: listLabel("i-", 3) is "iii-", listLabel("(a)", 2) is "(b)". */
export function listLabel(marker: ListMarker, n: number): string {
  const kind = marker.replace(/[^1aAiI]/g, "");
  const value =
    kind === "1"
      ? String(n)
      : kind === "a"
        ? letters(n)
        : kind === "A"
          ? letters(n).toUpperCase()
          : kind === "i"
            ? roman(n)
            : roman(n).toUpperCase();
  return marker.replace(kind, value);
}

/** The width of the label column, in `ch`, for items start .. start+count-1 (the longest label, plus a space). */
export function labelWidth(
  marker: ListMarker,
  start: number,
  count: number,
): number {
  let w = 0;
  for (let n = start; n < start + count; n++)
    w = Math.max(w, listLabel(marker, n).length);
  return w + 1;
}

const LABEL =
  /^(\((?:[a-z]|[ivx]{1,5}|\d{1,2})\)|(?:[a-z]|[ivx]{1,5}|\d{1,2})[)\-–]|\d{1,2}\.)[ \t]+(?=\S)/;

/** A paragraph the book starts with an item label: ["(a)", "In electroporation, …"]. Null for any other paragraph, or
 * when a marked book error starts inside the label (the mark stays whole). */
export function splitLabel(
  text: string,
  marks: string[] = [],
): [string, string] | null {
  const m = LABEL.exec(text);
  if (!m) return null;
  const rest = text.slice(m[0].length);
  if (/^\d/.test(rest) && m[1].endsWith(".")) return null; // "1. 5 g of …" is a number, not a label
  if (marks.some((k) => text.includes(k) && !rest.includes(k))) return null;
  return [m[1], rest];
}
