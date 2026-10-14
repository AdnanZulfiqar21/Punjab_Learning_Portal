// OCT14-04 (review of 2026-10-14): pages kept on the phone survive interrupted and failed writes. Host-side tests of
// the storage rules (src/lib/page-drafts-core.ts) against an in-memory file system with injected faults. This is not
// device evidence: real interruption on Android and iOS is still to be tested on devices (B09, B14).
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { createPageDrafts, type DraftFs, StorageLow } from "../src/lib/page-drafts-core.ts";

type Fault = "truncate-then-throw" | "throw" | "no-space";

class MemoryFs implements DraftFs {
  files = new Map<string, Uint8Array>();
  dirs = new Set<string>();
  free: number | null = 10_000_000_000;
  writeFault: ((path: string) => Fault | null) | null = null;
  copyFault: Fault | null = null;
  sources = new Map<string, Uint8Array>();

  key(path: string[]): string {
    return path.join("/");
  }
  exists(path: string[]): boolean {
    const k = this.key(path);
    return this.files.has(k) || this.dirs.has(k);
  }
  makeDir(path: string[]): void {
    for (let i = 1; i <= path.length; i++) this.dirs.add(this.key(path.slice(0, i)));
  }
  list(path: string[]): string[] {
    const prefix = `${this.key(path)}/`;
    return [...this.files.keys()].filter((k) => k.startsWith(prefix) && !k.slice(prefix.length).includes("/")).map((k) => k.slice(prefix.length));
  }
  readText(path: string[]): string {
    const f = this.files.get(this.key(path));
    if (!f) throw new Error("missing");
    return new TextDecoder().decode(f);
  }
  readHead(path: string[], bytes: number): Uint8Array {
    const f = this.files.get(this.key(path));
    if (!f) throw new Error("missing");
    return f.slice(0, bytes);
  }
  size(path: string[]): number {
    return this.files.get(this.key(path))?.length ?? 0;
  }
  writeText(path: string[], text: string): void {
    const data = new TextEncoder().encode(text);
    const fault = this.writeFault?.(this.key(path)) ?? null;
    if (fault === "truncate-then-throw") {
      this.files.set(this.key(path), data.slice(0, Math.max(1, Math.floor(data.length / 2))));
      throw new Error("I/O error");
    }
    if (fault === "no-space") throw new Error("ENOSPC: no space left on device");
    if (fault === "throw") throw new Error("I/O error");
    this.files.set(this.key(path), data);
  }
  rename(path: string[], newName: string): void {
    const from = this.key(path);
    const f = this.files.get(from);
    if (!f) throw new Error("missing");
    this.files.delete(from);
    this.files.set(this.key([...path.slice(0, -1), newName]), f);
  }
  async copyIn(uri: string, path: string[]): Promise<void> {
    const src = this.sources.get(uri);
    if (!src) throw new Error("no such source");
    if (this.copyFault === "truncate-then-throw") {
      this.files.set(this.key(path), src.slice(0, Math.floor(src.length / 2)));
      throw new Error("I/O error");
    }
    if (this.copyFault === "no-space") {
      this.files.set(this.key(path), src.slice(0, 3));
      throw new Error("ENOSPC: no space left on device");
    }
    this.files.set(this.key(path), src.slice());
  }
  remove(path: string[]): void {
    const k = this.key(path);
    this.files.delete(k);
    for (const f of [...this.files.keys()]) if (f.startsWith(`${k}/`)) this.files.delete(f);
    for (const d of [...this.dirs]) if (d === k || d.startsWith(`${k}/`)) this.dirs.delete(d);
  }
  uri(path: string[]): string {
    return `memory://${this.key(path)}`;
  }
  freeSpace(): number | null {
    return this.free;
  }
}

const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3, 4, 5, 6, 7, 8]);
const PDF = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x37]);
let fs: MemoryFs;
let ids: number;
let drafts: ReturnType<typeof createPageDrafts>;
const OWNER = "learner-1";
const TEST = "attempt-1";
const pageFiles = () => [...fs.files.keys()].filter((k) => /\/[a-z0-9]{6,40}$/.test(k));

beforeEach(() => {
  fs = new MemoryFs();
  fs.sources.set("cache://photo.jpg", JPEG);
  fs.sources.set("cache://script.pdf", PDF);
  ids = 0;
  drafts = createPageDrafts(fs, (o) => `scope-${o}`, () => `page${String(++ids).padStart(4, "0")}`, () => new Date("2026-10-14T05:00:00Z"));
});

describe("keeping a page", () => {
  it("copies the page in completely before it counts, then writes its record", async () => {
    const d = await drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "Page 1", mimeType: "image/jpeg", size: JPEG.length });
    assert.equal(d.bytes, JPEG.length);
    assert.deepEqual(drafts.listPages(OWNER, TEST).map((p) => [p.id, p.name, p.mimeType, p.recovered]), [["page0001", "Page 1", "image/jpeg", undefined]]);
    assert.equal(fs.list(["page-drafts", "scope-learner-1", TEST]).some((n) => n.endsWith(".part") || n.endsWith(".tmp")), false);
  });

  it("refuses before copying when the phone is nearly full, and when the copy runs out of space", async () => {
    fs.free = 10_000_000;
    await assert.rejects(drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "p", mimeType: "image/jpeg" }), StorageLow);
    assert.equal(fs.files.size, 0);
    fs.free = null;
    fs.copyFault = "no-space";
    await assert.rejects(drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "p", mimeType: "image/jpeg" }), StorageLow);
    assert.deepEqual(drafts.listPages(OWNER, TEST), []); // nothing half-copied is ever offered as a page
    assert.deepEqual(pageFiles(), []);
  });

  it("drops a copy interrupted part-way: half a page never counts as a page", async () => {
    fs.copyFault = "truncate-then-throw";
    await assert.rejects(drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "p", mimeType: "image/jpeg" }));
    assert.deepEqual(drafts.listPages(OWNER, TEST), []);
    assert.deepEqual([...fs.files.keys()].filter((k) => k.endsWith(".part")), []);
  });

  it("keeps the page when only its record can't be written; it is listed as a recovered page", async () => {
    fs.writeFault = (p) => (p.endsWith(".json.tmp") ? "no-space" : null);
    const d = await drafts.keepPage(OWNER, TEST, { uri: "cache://script.pdf", name: "Script", mimeType: "application/pdf" });
    fs.writeFault = null;
    const [only] = drafts.listPages(OWNER, TEST);
    assert.equal(only.id, d.id);
    assert.equal(only.recovered, true);
    assert.equal(only.mimeType, "application/pdf"); // worked out from the file itself
    assert.match(only.error ?? "", /details were lost/);
  });
});

describe("recovering after interrupted writes (OCT14-04)", () => {
  async function keepOne() {
    return drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "Page 1", mimeType: "image/jpeg", size: JPEG.length });
  }

  it("an upload note cut off part-way loses only the note, on every later reopen", async () => {
    const d = await keepOne();
    fs.writeFault = () => "truncate-then-throw";
    drafts.notePageError(OWNER, TEST, d, "That didn't upload. Check your connection.");
    fs.writeFault = null;
    for (let reopen = 0; reopen < 3; reopen++) {
      const pages = drafts.listPages(OWNER, TEST);
      assert.deepEqual(pages.map((p) => [p.id, p.name, p.recovered]), [[d.id, "Page 1", undefined]]);
    }
    assert.equal(fs.size(["page-drafts", "scope-learner-1", TEST, d.id]), JPEG.length); // the page itself is intact
  });

  it("a damaged record never makes the page a deletion candidate", async () => {
    const d = await keepOne();
    const record = ["page-drafts", "scope-learner-1", TEST, `${d.id}.json`];
    fs.files.set(fs.key(record), new TextEncoder().encode('{"id":"page0001","na')); // truncated on disk
    for (let reopen = 0; reopen < 3; reopen++) {
      const [only, ...rest] = drafts.listPages(OWNER, TEST);
      assert.equal(rest.length, 0);
      assert.equal(only.id, d.id);
      assert.equal(only.recovered, true);
      assert.equal(only.mimeType, "image/jpeg");
    }
    assert.equal(fs.size(["page-drafts", "scope-learner-1", TEST, d.id]), JPEG.length);
  });

  it("a damaged note is ignored, and a later note can still be written", async () => {
    const d = await keepOne();
    fs.files.set(fs.key(["page-drafts", "scope-learner-1", TEST, `${d.id}.note.json`]), new TextEncoder().encode("{oops"));
    assert.equal(drafts.listPages(OWNER, TEST)[0].error, undefined);
    drafts.notePageError(OWNER, TEST, d, "Server busy");
    assert.equal(drafts.listPages(OWNER, TEST)[0].error, "Server busy");
  });

  it("tidies only leftovers of interrupted writes and records whose page is gone", async () => {
    const d = await keepOne();
    const dir = ["page-drafts", "scope-learner-1", TEST];
    fs.files.set(fs.key([...dir, "page9999.part"]), JPEG.slice(0, 3));
    fs.files.set(fs.key([...dir, `${d.id}.note.json.tmp`]), new TextEncoder().encode("{"));
    fs.files.set(fs.key([...dir, "page8888.json"]), new TextEncoder().encode('{"id":"page8888"}'));
    assert.deepEqual(drafts.listPages(OWNER, TEST).map((p) => p.id), [d.id]);
    assert.deepEqual(fs.list(dir).sort(), [d.id, `${d.id}.json`]);
  });

  it("reads records written by the first version of the app", async () => {
    const dir = ["page-drafts", "scope-learner-1", TEST];
    fs.makeDir(dir);
    fs.files.set(fs.key([...dir, "oldpage01"]), JPEG);
    const old = { id: "oldpage01", name: "Old", mimeType: "image/jpeg", bytes: JPEG.length, savedAt: "2026-10-13T00:00:00Z", uri: "x", error: "Timed out" };
    fs.files.set(fs.key([...dir, "oldpage01.json"]), new TextEncoder().encode(JSON.stringify(old)));
    const [p] = drafts.listPages(OWNER, TEST);
    assert.deepEqual([p.id, p.name, p.error, p.recovered], ["oldpage01", "Old", "Timed out", undefined]);
  });
});

describe("removing pages", () => {
  it("removes a page only when sent or chosen by the learner, with its record and note", async () => {
    const d = await drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "p", mimeType: "image/jpeg" });
    drafts.notePageError(OWNER, TEST, d, "x");
    drafts.removePage(OWNER, TEST, d.id);
    assert.deepEqual(fs.list(["page-drafts", "scope-learner-1", TEST]), []);
  });

  it("keeps each account's pages apart, and sign-out removes all of them", async () => {
    await drafts.keepPage("someone-else", TEST, { uri: "cache://photo.jpg", name: "theirs", mimeType: "image/jpeg" });
    await drafts.keepPage(OWNER, TEST, { uri: "cache://photo.jpg", name: "mine", mimeType: "image/jpeg" });
    assert.deepEqual(drafts.listPages(OWNER, TEST).map((p) => p.name), ["mine"]);
    drafts.clearAll();
    assert.equal(fs.files.size, 0);
  });
});
