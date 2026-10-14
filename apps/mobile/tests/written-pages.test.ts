// OCT14-01 (review of 2026-10-14): a written test can't be submitted while a page is unsent or anything is still
// moving, the gate holds against concurrent capture and retry, and a lost submit response recovers the same receipt.
// Host-side tests of src/lib/written-pages.ts with injected storage, network and timing; not device evidence.
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import type { PageDraft, PageSource } from "../src/lib/page-drafts-core.ts";
import { WrittenPages } from "../src/lib/written-pages.ts";

type Deferred<T> = { promise: Promise<T>; resolve: (v: T) => void; reject: (e: unknown) => void };
function deferred<T>(): Deferred<T> {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
const tick = () => new Promise((r) => setTimeout(r, 0));

let calls: { kept: string[]; removed: string[]; notes: [string, string][]; uploads: string[]; seals: [string, number][] };
let uploadPlan: (draft: PageDraft) => Promise<void>;
let sealPlan: (key: string, revision: number) => Promise<unknown>;
let keepPlan: (source: PageSource) => Promise<PageDraft>;
let n: number;

function pages(kept: PageDraft[] = []) {
  return new WrittenPages(
    {
      keepPage: (s) => keepPlan(s),
      removePage: (id) => void calls.removed.push(id),
      notePageError: (d, e) => void calls.notes.push([d.id, e]),
      upload: (d) => {
        calls.uploads.push(d.id);
        return uploadPlan(d);
      },
      seal: (key, revision) => {
        calls.seals.push([key, revision]);
        return sealPlan(key, revision);
      },
      message: (e, fallback) => (e instanceof Error && e.message ? e.message : fallback),
      newKey: () => `key-${++n}`,
    },
    kept,
  );
}
const photo = (name = "photo.jpg"): PageSource => ({ uri: `cache://${name}`, name, mimeType: "image/jpeg", size: 1000 });
const kept = (id: string): PageDraft => ({ id, name: id, mimeType: "image/jpeg", bytes: 10, savedAt: "2026-10-14T00:00:00Z", uri: `file://${id}` });

beforeEach(() => {
  calls = { kept: [], removed: [], notes: [], uploads: [], seals: [] };
  n = 0;
  keepPlan = async (s) => {
    calls.kept.push(s.name);
    return kept(`kept-${s.name}`);
  };
  uploadPlan = async () => {};
  sealPlan = async (key) => ({ receipt: `receipt-for-${key}` });
});

describe("the submit gate (OCT14-01)", () => {
  it("refuses with every part mapped while one page failed to upload, and seals nothing", async () => {
    const p = pages();
    await p.capture(photo("a.jpg"));
    uploadPlan = async () => {
      throw new Error("Network request failed");
    };
    await p.capture(photo("b.jpg"));
    assert.equal(p.pending.length, 1);
    assert.equal(p.pending[0].status, "failed");
    const out = await p.seal(3, 3, 7);
    assert.equal(out.ok, false);
    assert.match(out.ok ? "" : out.reason, /on this phone but not sent/);
    assert.deepEqual(calls.seals, []);
    assert.deepEqual(calls.notes, [["kept-b.jpg", "Network request failed"]]); // the reason is kept with the page
    assert.deepEqual(calls.removed, ["kept-a.jpg"]); // only the page the server has was removed
  });

  it("can't be passed while a capture is still uploading, even though the button was enabled when pressed", async () => {
    const p = pages();
    const upload = deferred<void>();
    uploadPlan = () => upload.promise;
    const capturing = p.capture(photo());
    await tick();
    assert.equal((await p.seal(3, 3, 1)).ok, false); // the click raced the capture: refused at the moment of sealing
    assert.equal(p.canCapture(), true);
    upload.resolve();
    await capturing;
    const out = await p.seal(3, 3, 1);
    assert.equal(out.ok, true);
    assert.deepEqual(calls.seals, [["key-1", 1]]);
  });

  it("can't be passed while the camera or file picker is open, or a page is being turned or the map saved", async () => {
    const p = pages();
    const work = deferred<void>();
    const tracked = p.track(() => work.promise);
    assert.match(p.blocker(3, 3) ?? "", /finished uploading and saving/);
    assert.equal((await p.seal(3, 3, 1)).ok, false);
    work.resolve();
    await tracked;
    assert.equal(p.blocker(3, 3), null);
  });

  it("can't be passed while a retry is in flight; a successful retry then allows exactly one submission", async () => {
    uploadPlan = async () => {
      throw new Error("offline");
    };
    const p = pages();
    await p.capture(photo());
    const retry = deferred<void>();
    uploadPlan = () => retry.promise;
    const retrying = p.resend("kept-photo.jpg");
    await tick();
    assert.equal((await p.seal(1, 1, 1)).ok, false);
    retry.resolve();
    await retrying;
    const [first, second] = await Promise.all([p.seal(1, 1, 1), p.seal(1, 1, 1)]); // a double tap
    assert.equal(first.ok, true);
    assert.equal(second.ok, false);
    assert.equal(calls.seals.length, 1);
  });

  it("allows submission once the learner removes the page they don't want", async () => {
    uploadPlan = async () => {
      throw new Error("offline");
    };
    const p = pages();
    await p.capture(photo());
    p.discard("kept-photo.jpg");
    assert.deepEqual(calls.removed, ["kept-photo.jpg"]);
    assert.equal((await p.seal(2, 2, 4)).ok, true);
  });

  it("pages left from an earlier session must be sent or removed first", async () => {
    const p = pages([kept("left-1")]);
    assert.match(p.blocker(1, 1) ?? "", /1 page is on this phone/);
    await p.resend("left-1");
    assert.equal(p.blocker(1, 1), null);
    assert.deepEqual(calls.removed, ["left-1"]);
  });

  it("recovers the same receipt after a lost response, using the same submission key", async () => {
    const p = pages();
    let attempt = 0;
    sealPlan = async (key) => {
      attempt += 1;
      if (attempt === 1) throw new Error("The connection was lost before the receipt arrived.");
      return { receipt: `receipt-for-${key}` };
    };
    const lost = await p.seal(1, 1, 2);
    assert.equal(lost.ok, false);
    const again = await p.seal(1, 1, 2);
    assert.deepEqual(again, { ok: true, receipt: { receipt: "receipt-for-key-1" } });
    assert.deepEqual(calls.seals, [["key-1", 2], ["key-1", 2]]);
  });

  it("after submitting, nothing more can be added or submitted from this screen", async () => {
    const p = pages();
    assert.equal((await p.seal(1, 1, 1)).ok, true);
    assert.equal(p.canCapture(), false);
    await p.capture(photo());
    assert.deepEqual(calls.kept, []);
    assert.equal((await p.seal(1, 1, 1)).ok, false);
  });

  it("still requires every part to be mapped", async () => {
    assert.match(pages().blocker(2, 3) ?? "", /Every part needs a page/);
  });
});

describe("capturing", () => {
  it("sends a page straight away when it can't be kept for lack of space, and says so", async () => {
    keepPlan = async () => {
      throw Object.assign(new Error("Your phone is nearly full."), { freeBytes: 12_000_000 });
    };
    uploadPlan = async () => {
      throw new Error("offline");
    };
    const p = pages();
    await p.capture(photo());
    assert.equal(p.lowStorage, 12_000_000);
    assert.equal(p.pending[0].kept, false);
    assert.deepEqual(calls.notes, []); // nothing on the phone to annotate
  });

  it("refuses files that aren't JPEG, PNG or PDF, or are too large, before keeping anything", async () => {
    const p = pages();
    await p.capture({ uri: "cache://x.heic", name: "x.heic", mimeType: "image/heic", size: 10 });
    await p.capture({ uri: "cache://big.jpg", name: "big.jpg", mimeType: "image/jpeg", size: 16 * 1024 * 1024 });
    assert.deepEqual(calls.kept, []);
    assert.match(p.notice ?? "", /limit is 15 MB/);
  });
});
