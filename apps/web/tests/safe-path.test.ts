// SECURITY-HARDEN-01: every redirect to a path that came from a request or the API goes through one check, so none of
// them can be turned into an open redirect. Host-side tests of src/lib/safe-path.ts.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { safeAppPath } from "../src/lib/safe-path.ts";

describe("safeAppPath", () => {
  it("keeps same-site paths", () => {
    for (const p of [
      "/account",
      "/learn/chapter/1?lang=en#lesson-2",
      "/notifications",
    ])
      assert.equal(safeAppPath(p, "/x"), p);
  });
  it("refuses other sites and tricks browsers read as other sites", () => {
    for (const p of [
      "//evil.example",
      "/\\evil.example",
      "/\t/evil.example",
      "/\n/evil",
      "https://evil.example",
      "javascript:alert(1)",
      "",
      "evil",
      "\\\\evil",
    ])
      assert.equal(safeAppPath(p, "/fallback"), "/fallback", JSON.stringify(p));
  });
  it("treats anything that is not a string as missing", () => {
    assert.equal(safeAppPath(null, "/account"), "/account");
    assert.equal(safeAppPath(undefined, "/account"), "/account");
  });
});
