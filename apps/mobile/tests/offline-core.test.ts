// P13.S3.T1-T3 (OFFLINE-CORE-01): the offline progress queue and study pack rules, run on the host with injected
// storage and sending. Not device evidence: files, crypto and process death on a phone wait on B09/B14.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createFlusher, withOp, type ProgressOp, type QueueStore } from "../src/lib/progress-queue-core.ts";
import { afterStatus, downloadProblem, fileProblem, PACK_FORMAT, usable } from "../src/lib/study-packs-core.ts";

function memory(initial: ProgressOp[] = []): QueueStore & { writes: number } {
  let ops = [...initial];
  return {
    writes: 0,
    read: () => [...ops],
    write(next) {
      this.writes += 1;
      ops = [...next];
    },
  };
}
const at = new Date("2026-10-15T00:00:00Z");
const temporary = (e: unknown) => e instanceof Error && e.message === "offline";

describe("the progress queue (P13.S3.T2)", () => {
  it("keeps one change per lesson and kind, the newest last", () => {
    let ops = withOp([], { kind: "note", lesson_id: "l1", text: "first", base: 1 }, "a", at);
    ops = withOp(ops, { kind: "completion", lesson_id: "l1", done: true }, "b", at);
    ops = withOp(ops, { kind: "note", lesson_id: "l1", text: "second", base: 1 }, "c", at);
    assert.deepEqual(ops.map((o) => o.op_id), ["b", "c"]);
    assert.equal(ops[1].kind === "note" && ops[1].text, "second");
  });

  it("sends in order and empties the queue", async () => {
    const store = memory();
    store.write(withOp(withOp([], { kind: "completion", lesson_id: "l1", done: true }, "a", at), { kind: "completion", lesson_id: "l2", done: true }, "b", at));
    const sent: string[] = [];
    const n = await createFlusher(store, async (op) => void sent.push(op.op_id), temporary)();
    assert.equal(n, 2);
    assert.deepEqual(sent, ["a", "b"]);
    assert.deepEqual(store.read(), []);
  });

  it("stops at a temporary failure and keeps everything from there on", async () => {
    const store = memory();
    for (const [i, l] of ["l1", "l2", "l3"].entries()) store.write(withOp(store.read(), { kind: "completion", lesson_id: l, done: true }, `op${i}`, at));
    const n = await createFlusher(
      store,
      async (op) => {
        if (op.lesson_id === "l2") throw new Error("offline");
      },
      temporary,
    )();
    assert.equal(n, 1);
    assert.deepEqual(store.read().map((o) => o.op_id), ["op1", "op2"]); // the failed one and everything after it
  });

  it("drops an operation that can no longer apply (a note changed elsewhere) and goes on", async () => {
    const store = memory();
    store.write(withOp(store.read(), { kind: "note", lesson_id: "l1", text: "mine", base: 3 }, "n", at));
    store.write(withOp(store.read(), { kind: "completion", lesson_id: "l2", done: true }, "c", at));
    const n = await createFlusher(
      store,
      async (op) => {
        if (op.kind === "note") throw new Error("conflict");
      },
      temporary,
    )();
    assert.equal(n, 1);
    assert.deepEqual(store.read(), []);
  });

  it("runs one flush at a time: a second call joins the first", async () => {
    const store = memory();
    store.write(withOp([], { kind: "completion", lesson_id: "l1", done: true }, "a", at));
    let release!: () => void;
    let calls = 0;
    const flush = createFlusher(
      store,
      () => {
        calls += 1;
        return new Promise<void>((r) => (release = r));
      },
      temporary,
    );
    const first = flush();
    const second = flush();
    assert.equal(first, second);
    await new Promise((r) => setTimeout(r, 0));
    release();
    assert.equal(await first, 1);
    assert.equal(calls, 1);
  });

  it("a change queued while flushing is kept for the next flush", async () => {
    const store = memory();
    store.write(withOp([], { kind: "completion", lesson_id: "l1", done: true }, "a", at));
    const n = await createFlusher(
      store,
      async () => {
        store.write(withOp(store.read(), { kind: "completion", lesson_id: "l9", done: true }, "late", at));
      },
      temporary,
    )();
    assert.equal(n, 1); // a flush sends what was queued when it started
    assert.deepEqual(store.read().map((o) => o.op_id), ["late"]); // the late change isn't lost: it waits for the next
  });
});

describe("study packs (P13.S3.T1, T3)", () => {
  const manifest = { pack_format_version: PACK_FORMAT, expires_at: "2026-11-01T00:00:00Z", sha256: "abc", includes_premium: true, files: [] };

  it("keeps a download only in a format this build reads and with a matching checksum", () => {
    assert.equal(downloadProblem(manifest, "abc"), null);
    assert.match(downloadProblem(manifest, "xyz") ?? "", /damaged/);
    assert.match(downloadProblem({ ...manifest, pack_format_version: PACK_FORMAT + 1 }, "abc") ?? "", /newer version of the app/);
    assert.equal(fileProblem("f1", "f1"), null);
    assert.match(fileProblem("f1", "f2") ?? "", /damaged/);
    assert.equal(fileProblem(null, "anything"), null);
  });

  it("opens a stored pack only until it expires, and never one too new for this build", () => {
    assert.equal(usable(manifest, at), "ok");
    assert.equal(usable(manifest, new Date("2026-11-01T00:00:00Z")), "expired"); // at the expiry instant it is gone
    assert.equal(usable({ ...manifest, pack_format_version: PACK_FORMAT + 1 }, at), "too_new");
  });

  it("drops a pack the server says can't be kept, or premium material the plan no longer covers", () => {
    assert.equal(afterStatus(manifest, { keep: true, includes_premium: true }), "kept");
    assert.equal(afterStatus(manifest, { keep: false, includes_premium: true }), "removed");
    assert.equal(afterStatus(manifest, { keep: true, includes_premium: false }), "removed");
    assert.equal(afterStatus({ ...manifest, includes_premium: false }, { keep: true, includes_premium: false }), "kept");
  });
});
