// P15.S3.T1 (MOBILE-SCREENSHOTS-01): the phone refuses what the server would refuse, before uploading anything.
// Host-side tests of src/lib/screenshots.ts; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { MAX_SCREENSHOT_BYTES, screenshotProblem } from "../src/lib/screenshots.ts";

describe("help screenshots", () => {
  it("accepts JPEG and PNG up to 5 MB", () => {
    assert.equal(screenshotProblem({ mimeType: "image/png", fileSize: 200_000 }), null);
    assert.equal(screenshotProblem({ mimeType: "image/jpeg", fileSize: MAX_SCREENSHOT_BYTES }), null);
    assert.equal(screenshotProblem({}), null); // unknown: the server decides
  });

  it("refuses other types and larger files", () => {
    assert.match(screenshotProblem({ mimeType: "image/heic", fileSize: 10 }) ?? "", /JPEG or PNG/);
    assert.match(screenshotProblem({ mimeType: "image/png", fileSize: MAX_SCREENSHOT_BYTES + 1 }) ?? "", /5 MB/);
  });

  it("uses the API's limit", () => {
    const service = readFileSync(new URL("../../api/src/portal_api/modules/support/service.py", import.meta.url), "utf8");
    const m = /MAX_SCREENSHOT_BYTES\s*=\s*(\d+)\s*\*\s*1024\s*\*\s*1024/.exec(service);
    assert.ok(m, "MAX_SCREENSHOT_BYTES not found in the API");
    assert.equal(Number(m[1]) * 1024 * 1024, MAX_SCREENSHOT_BYTES);
  });
});
