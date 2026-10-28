// CODE-HIGHLIGHT-01: a printed program's parts are coloured apart (src/lib/code-highlight.ts). Host-side tests; not
// device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { markPieces } from "../src/lib/book-errors.ts";
import { codeRuns, codeTokens } from "../src/lib/code-highlight.ts";

const kinds = (text: string) => codeTokens(text, "python").filter((t) => t.kind !== "plain").map((t) => `${t.kind}:${t.text}`);

describe("program colouring", () => {
  it("tells comments, keywords, constants, strings, calls and variables apart", () => {
    assert.deepEqual(kinds('logical_or = x or y  # True or False\nprint(x, "or", 2.5)'), [
      "variable:logical_or",
      "variable:x",
      "keyword:or",
      "variable:y",
      "comment:# True or False",
      "function:print",
      "variable:x",
      'string:"or"',
      "number:2.5",
    ]);
    assert.deepEqual(kinds("x = True\ndef area(r):\n    return None"), [
      "variable:x",
      "constant:True",
      "keyword:def",
      "function:area",
      "variable:r",
      "keyword:return",
      "constant:None",
    ]);
  });

  it("keeps a # or a keyword inside a string as string", () => {
    assert.deepEqual(kinds("s = 'a # not and'"), ["variable:s", "string:'a # not and'"]);
  });

  it("leaves other languages plain and loses no text", () => {
    assert.deepEqual(codeTokens("True and False", "text"), [{ text: "True and False", kind: "plain" }]);
    const src = 'a=1\nprint("hi")  # done\n';
    assert.equal(
      codeTokens(src, "Python")
        .map((t) => t.text)
        .join(""),
      src,
    );
  });

  it("keeps a book error in red across coloured pieces", () => {
    const src = "print(x) # Output: True and False = True";
    const runs = codeRuns(src, "python", markPieces(src, ["# Output: True and False = True"]));
    assert.equal(runs.map((r) => r.text).join(""), src);
    assert.deepEqual(
      runs.filter((r) => r.error).map((r) => r.text),
      ["# Output: True and False = True"],
    );
    assert.equal(runs[0].kind, "function");
  });

  it("is the same file in web and mobile", () => {
    const mobile = readFileSync(new URL("../src/lib/code-highlight.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/code-highlight.ts", import.meta.url), "utf8");
    assert.equal(mobile, web);
  });
});
