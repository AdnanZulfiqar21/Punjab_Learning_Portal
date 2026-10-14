// The written screen's pages and its submit gate (CAPTURE-01; OCT14-01). Plain TypeScript with no runtime imports, so
// the rules are tested on the host with injected storage, network and timing (tests/written-pages.test.ts).
//
// A page is kept on the phone first (keepPage), then sent. Until the server has it, it is "on this phone, not sent
// yet", with Send again and Remove. Submitting is refused, in the submit call itself and not just by a disabled
// button, while anything is still moving (choosing, copying, sending, saving the answer map, turning a page) or any
// page is still unsent: a learner can't seal a script that leaves work behind on the phone. One submission key is
// kept for the whole session, so a retry after a lost response gets the same receipt.
import type { PageDraft, PageSource } from "./page-drafts-core";

export type Pending = PageDraft & { status: "sending" | "failed"; kept: boolean };

export type PagesDeps = {
  keepPage(source: PageSource): Promise<PageDraft>; // throws an error with `freeBytes` when the phone is too full
  removePage(id: string): void;
  notePageError(draft: PageDraft, error: string): void;
  upload(draft: PageDraft): Promise<void>; // the server has it once this resolves
  seal(key: string, revision: number): Promise<unknown>; // the receipt; the same key always gets the same receipt
  message(error: unknown, fallback: string): string;
  newKey(): string;
};

export const ACCEPTED = new Set(["image/jpeg", "image/png", "application/pdf"]);
export const MAX_BYTES: Record<string, number> = {
  "application/pdf": 40 * 1024 * 1024,
  "image/jpeg": 15 * 1024 * 1024,
  "image/png": 15 * 1024 * 1024,
};
const mb = (n: number) => `${Math.max(1, Math.round(n / (1024 * 1024)))} MB`;

export type SealResult = { ok: true; receipt: unknown } | { ok: false; reason: string };

export class WrittenPages {
  #deps: PagesDeps;
  #pending: Pending[];
  #busy = 0;
  #sealing = false;
  #sealed = false; // submitted: nothing more can be added or submitted from this screen
  #sealKey: string;
  #listeners = new Set<() => void>();
  #version = 0; // changes whenever anything shown changes (useSyncExternalStore)
  lowStorage: number | null | undefined = undefined; // free bytes, when a page couldn't be kept for lack of space
  notice: string | null = null; // the last problem with a page, for the screen

  constructor(deps: PagesDeps, kept: PageDraft[]) {
    this.#deps = deps;
    this.#pending = kept.map((d) => ({ ...d, status: "failed", kept: true, error: d.error ?? "Not sent yet." }));
    this.#sealKey = deps.newKey(); // one key for this submission; a retry returns the same receipt
  }

  get pending(): readonly Pending[] {
    return this.#pending;
  }

  get busy(): number {
    return this.#busy;
  }

  get sealing(): boolean {
    return this.#sealing;
  }

  get version(): number {
    return this.#version;
  }

  subscribe(listener: () => void): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }

  #changed(): void {
    this.#version += 1;
    for (const l of this.#listeners) l();
  }

  /** Count work in flight for the whole of `work`, so a submit started meanwhile sees it. */
  async track<T>(work: () => Promise<T>): Promise<T> {
    this.#busy += 1;
    this.#changed();
    try {
      return await work();
    } finally {
      this.#busy -= 1;
      this.#changed();
    }
  }

  /** Why submitting isn't possible right now, or null. */
  blocker(mapped: number, total: number): string | null {
    if (this.#sealed) return "Already submitted.";
    if (this.#sealing) return "Submitting…";
    if (this.#busy > 0) return "Wait until your pages have finished uploading and saving.";
    if (this.#pending.length > 0) {
      const n = this.#pending.length;
      return `${n} page${n === 1 ? " is" : "s are"} on this phone but not sent. Send ${n === 1 ? "it" : "them"} again, or remove any you don't need, before you submit.`;
    }
    if (mapped < total) return "Every part needs a page or \"I didn't answer this\".";
    return null;
  }

  /** Starting a capture is refused while submitting, so nothing can slip in after the gate was passed. */
  canCapture(): boolean {
    return !this.#sealing && !this.#sealed;
  }

  /** Keep a chosen page on the phone, then send it. A page that can't be kept is still sent, with a warning. */
  async capture(source: PageSource): Promise<void> {
    if (!this.canCapture()) return;
    await this.track(async () => {
      if (!ACCEPTED.has(source.mimeType)) {
        this.notice = `${source.name}: only JPEG, PNG or PDF files are accepted.`;
        return;
      }
      const limit = MAX_BYTES[source.mimeType];
      if (source.size && source.size > limit) {
        this.notice = `${source.name} is ${mb(source.size)}; the limit is ${mb(limit)}. Take a smaller photo or split the PDF.`;
        return;
      }
      let draft: PageDraft;
      let kept = true;
      try {
        draft = await this.#deps.keepPage(source);
        this.lowStorage = undefined;
      } catch (e) {
        if (e && typeof e === "object" && "freeBytes" in e) this.lowStorage = (e as { freeBytes: number | null }).freeBytes;
        else this.notice = "This page couldn't be kept on your phone, so it is being sent straight away.";
        kept = false;
        draft = {
          id: this.#deps.newKey(),
          name: source.name,
          mimeType: source.mimeType,
          bytes: source.size ?? 0,
          savedAt: new Date().toISOString(),
          uri: source.uri,
        };
      }
      await this.#send(draft, kept);
    });
  }

  /** Send a page again (also used for the pages left from an earlier session). */
  async resend(id: string): Promise<void> {
    const d = this.#pending.find((x) => x.id === id);
    if (!d || d.status === "sending" || !this.canCapture()) return;
    await this.track(() => this.#send(d, d.kept));
  }

  async #send(draft: PageDraft, kept: boolean): Promise<void> {
    this.#pending = [...this.#pending.filter((x) => x.id !== draft.id), { ...draft, status: "sending", kept, error: undefined }];
    this.#changed();
    try {
      await this.#deps.upload(draft);
      if (kept) this.#deps.removePage(draft.id); // the server has it now
      this.#pending = this.#pending.filter((x) => x.id !== draft.id);
    } catch (e) {
      const msg = this.#deps.message(e, "That didn't upload. Check your connection.");
      if (kept) this.#deps.notePageError(draft, msg);
      this.#pending = this.#pending.map((x) => (x.id === draft.id ? { ...x, status: "failed", error: msg } : x));
    }
    this.#changed();
  }

  /** The learner chose to remove a page that wasn't sent. */
  discard(id: string): void {
    const d = this.#pending.find((x) => x.id === id);
    if (!d || d.status === "sending") return;
    if (d.kept) this.#deps.removePage(d.id);
    this.#pending = this.#pending.filter((x) => x.id !== id);
    this.#changed();
  }

  /** Submit once. Re-checks the gate here, at the moment of submitting, whatever the button showed. */
  async seal(mapped: number, total: number, revision: number): Promise<SealResult> {
    const reason = this.blocker(mapped, total);
    if (reason) return { ok: false, reason };
    this.#sealing = true;
    this.#changed();
    try {
      const receipt = await this.#deps.seal(this.#sealKey, revision); // the server refuses a stale revision
      this.#sealed = true;
      return { ok: true, receipt };
    } catch (e) {
      return { ok: false, reason: this.#deps.message(e, "Couldn't submit. Your pages are still uploaded; try again.") };
    } finally {
      this.#sealing = false;
      this.#changed();
    }
  }
}
