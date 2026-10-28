// CODE-HIGHLIGHT-01: a printed program is shown with its parts in different colours (comments, keywords, strings,
// numbers, function names, variables), so a reader can tell them apart. Only Python is coloured; other languages
// (program output, pseudocode) stay plain. The book's wrong passages keep their red mark on top (BOOK-CORRECTION-01).
// Identical in apps/web and apps/mobile (a host test compares the two files).

export type CodeKind = "plain" | "comment" | "keyword" | "constant" | "string" | "number" | "function" | "variable";
export type CodeRun = { text: string; kind: CodeKind; error: boolean };

const KEYWORDS = new Set(
  "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split(
    " ",
  ),
);
const CONSTANTS = new Set(["True", "False", "None"]);
const BUILTINS = new Set(
  "print input len range int float str bool list dict set tuple type abs min max sum round sorted enumerate zip open map filter isinstance".split(" "),
);

// Strings first (a # or a keyword inside quotes is text), then comments, numbers and names.
const TOKEN =
  /([rRbBfFuU]{0,2}(?:"""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)|"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?))|(#[^\n]*)|(\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)/g;

/** The program split into coloured pieces. */
export function codeTokens(text: string, language: string): { text: string; kind: CodeKind }[] {
  if (!/^py(thon)?\d?$/i.test(language.trim())) return [{ text, kind: "plain" }];
  const out: { text: string; kind: CodeKind }[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ text: text.slice(last, at), kind: "plain" });
    let kind: CodeKind;
    if (m[1] !== undefined) kind = "string";
    else if (m[2] !== undefined) kind = "comment";
    else if (m[3] !== undefined) kind = "number";
    else {
      const name = m[4];
      kind = KEYWORDS.has(name)
        ? "keyword"
        : CONSTANTS.has(name)
          ? "constant"
          : BUILTINS.has(name) || /^\s*\(/.test(text.slice(at + name.length))
            ? "function"
            : "variable";
    }
    out.push({ text: m[0], kind });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), kind: "plain" });
  return out;
}

/** The coloured pieces cut again where a book error starts or ends, so a red mark can sit over any colour. `errors` is
 * the text split by `markPieces` (lib/book-errors.ts). */
export function codeRuns(text: string, language: string, errors: { text: string; error: boolean }[]): CodeRun[] {
  const runs: CodeRun[] = [];
  let e = 0; // index into errors
  let eLeft = errors[0]?.text.length ?? 0; // characters left in errors[e]
  for (const token of codeTokens(text, language)) {
    let rest = token.text;
    while (rest.length) {
      while (eLeft === 0 && e < errors.length - 1) eLeft = errors[++e].text.length;
      const take = Math.min(rest.length, eLeft || rest.length);
      const error = errors[e]?.error ?? false;
      const prev = runs[runs.length - 1];
      if (prev && prev.kind === token.kind && prev.error === error) prev.text += rest.slice(0, take);
      else runs.push({ text: rest.slice(0, take), kind: token.kind, error });
      rest = rest.slice(take);
      eLeft -= take;
    }
  }
  return runs;
}
