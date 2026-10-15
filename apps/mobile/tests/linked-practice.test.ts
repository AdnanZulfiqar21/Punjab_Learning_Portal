// W04.S3.T3 (MOBILE-LINKED-01): host-side tests of src/lib/linked-practice.ts; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { canStart, LINKED_REASON, linkedRoute, togglePosition } from "../src/lib/linked-practice.ts";

describe("linked practice", () => {
  it("opens the started test, or the confirmation screen before it starts", () => {
    assert.deepEqual(linkedRoute({ attempt_id: "a1", form_id: "f1" }), { pathname: "/written/[id]", params: { id: "a1" } });
    assert.deepEqual(linkedRoute({ attempt_id: null, form_id: "f1" }), { pathname: "/written/linked/[formId]", params: { formId: "f1" } });
  });

  it("only offers to start when the allowance covers it", () => {
    assert.equal(canStart({ allowance_available: 2, allowance_units: 2 }), true);
    assert.equal(canStart({ allowance_available: 1, allowance_units: 2 }), false);
  });

  it("keeps the picked questions in order", () => {
    assert.deepEqual(togglePosition([1, 3], 2), [1, 2, 3]);
    assert.deepEqual(togglePosition([1, 2, 3], 2), [1, 3]);
  });

  it("explains every reason the server can give", () => {
    for (const reason of ["REWRITE", "NEW_CONTENT", "INDETERMINATE"]) assert.ok(LINKED_REASON[reason]);
  });
});
