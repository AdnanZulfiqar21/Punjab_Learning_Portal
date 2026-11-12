// CHAPTER-MOCK-01 / BOOK-MOCK-01: the phone builds a mock test with the same code as the web, so the same test number is
// the same paper on both (src/lib/chapter-mocks.ts, src/lib/book-mocks.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

describe("mock test papers", () => {
  for (const file of ["chapter-mocks.ts", "book-mocks.ts"]) {
    it(`${file} is the same file on web and app`, () => {
      const mobile = readFileSync(new URL(`../src/lib/${file}`, import.meta.url), "utf8");
      const web = readFileSync(new URL(`../../web/src/lib/${file}`, import.meta.url), "utf8");
      assert.equal(mobile, web);
    });
  }
});
