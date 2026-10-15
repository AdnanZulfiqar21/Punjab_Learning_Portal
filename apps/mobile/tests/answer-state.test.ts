// ANSWER-STATES-01 (roadmap §6.1, P10.S2, P13.S2.T2): the five answer states, and the same rules on web and mobile.
// Host-side tests of src/lib/answer-state.ts; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { answerState, PALETTE_LABEL, stateLine } from "../src/lib/answer-state.ts";

describe("answer states", () => {
  it("only a server receipt is saved; a local change is selected, then saving while sent", () => {
    assert.equal(answerState("pending", { sending: false, held: false }), "selected");
    assert.equal(answerState("pending", { sending: true, held: false }), "saving");
    assert.equal(answerState("saved", { sending: false, held: false }), "saved");
    assert.equal(answerState("empty", { sending: false, held: false }), "empty");
  });

  it("a change whose send failed, or from an earlier session, is pending until a send carries it again", () => {
    assert.equal(answerState("pending", { sending: false, held: true }), "pending");
    assert.equal(answerState("pending", { sending: true, held: true }), "saving");
  });

  it("a refusal stays a refusal whatever the connection is doing", () => {
    assert.equal(answerState("rejected", { sending: true, held: true }), "rejected");
    assert.equal(stateLine("rejected", { elsewhere: false, reason: "The test has ended." }), "Not saved: The test has ended.");
  });

  it("never reads a selection or a pending change as saved", () => {
    for (const s of ["selected", "saving", "pending"] as const) {
      assert.doesNotMatch(PALETTE_LABEL[s], /^saved/);
      assert.doesNotMatch(stateLine(s, { elsewhere: false }), /^Saved/);
    }
    assert.match(stateLine("pending", { elsewhere: true }), /until you continue here/);
  });

  it("web and mobile use the same file", () => {
    const mobile = readFileSync(new URL("../src/lib/answer-state.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/answer-state.ts", import.meta.url), "utf8");
    assert.equal(web, mobile);
  });
});
