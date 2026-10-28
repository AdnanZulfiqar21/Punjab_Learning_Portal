// CODE-RUNNER-01: only a program's plain values can be changed (src/lib/code-vars.ts). Host-side tests; not device
// evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { editableVars, inputPrompts, isPlainValue, withValues } from "../src/lib/code-vars.ts";

describe("changing a program's values", () => {
  it("knows a plain value", () => {
    for (const v of ["10", "-2.5", '"Ali"', "'a # b'", "True", "None", '["Mango", "Apple"]', "(1, 2, 'x', 4.5)", "{0: [1, 2], 1: []}", "[]"])
      assert.equal(isPlainValue(v), true, v);
    for (const v of ["x", "a + b", "int(input())", "(3 + 4) * 2", "random.randint(1, 10)", "[1, 2", "1, 2", "__import__('os')", "", '"open'])
      assert.equal(isPlainValue(v), false, v);
  });

  it("finds top-level assignments of plain values, keeping trailing comments", () => {
    const code = 'x = True\ny = False  # second\nz = x and y\nif x:\n    w = 3\nname = "a#b" # note\nn = int(input("Age: "))';
    assert.deepEqual(
      editableVars(code).map((v) => [v.line, v.name, v.value]),
      [
        [0, "x", "True"],
        [1, "y", "False"],
        [5, "name", '"a#b"'],
      ],
    );
  });

  it("puts new values in and nothing else", () => {
    const code = "a = 10\nb = 5  # five\nprint(a + b)";
    const vars = editableVars(code);
    assert.equal(withValues(code, vars, { 0: "7", 1: " 2 " }), "a = 7\nb = 2  # five\nprint(a + b)");
    assert.equal(withValues(code, vars, { 0: "print('hi')" }), code); // not a plain value: the printed one stays
  });

  it("reads Windows line ends too", () => {
    assert.deepEqual(
      editableVars("a = 1\r\nb = 2\r\nprint(a + b)").map((v) => [v.name, v.value]),
      [
        ["a", "1"],
        ["b", "2"],
      ],
    );
  });

  it("lists input prompts", () => {
    assert.deepEqual(inputPrompts('n = input("Enter your name: ")\nage = int(input())\nh = float(input(\'H: \'))'), ["Enter your name: ", "", "H: "]);
  });

  it("is the same file in web and mobile", () => {
    const mobile = readFileSync(new URL("../src/lib/code-vars.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/code-vars.ts", import.meta.url), "utf8");
    assert.equal(mobile, web);
  });
});
