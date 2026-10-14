// W03.S1.T2 (CAPTURE-01), hardened for OCT14-04: the rules for pages kept on the phone until they upload, written
// against a small file-system interface so they can be tested with injected faults (tests/page-drafts.test.ts).
// No runtime imports: the app binds it to expo-file-system (page-drafts.ts); the tests to an in-memory fake.
//
// Each page is three files in its test's folder:
//   <id>            the page itself. Copied in as <id>.part and renamed once complete, so it is never half a page.
//   <id>.json       what it is (name, type, size, when). Written once, through <id>.json.tmp and a rename.
//   <id>.note.json  why the last upload failed. Replaced through <id>.note.json.tmp and a rename; losing it loses
//                   only the note.
// Recovery never deletes a page: one whose record is missing or unreadable is shown as a recovered page, which the
// learner can send or remove. Only leftovers of interrupted writes (.part, .tmp) and records whose page is gone are
// tidied away.

export type PageSource = { uri: string; name: string; mimeType: string; size?: number | null };
export type PageDraft = {
  id: string;
  name: string;
  mimeType: string;
  bytes: number;
  savedAt: string;
  uri: string;
  error?: string;
  recovered?: boolean; // its record was lost; what it is was worked out from the file itself
};

export interface DraftFs {
  exists(path: string[]): boolean;
  makeDir(path: string[]): void; // with parents
  list(path: string[]): string[]; // file names in a folder
  readText(path: string[]): string;
  readHead(path: string[], bytes: number): Uint8Array;
  size(path: string[]): number;
  writeText(path: string[], text: string): void; // may fail part-way
  rename(path: string[], newName: string): void; // in the same folder, replacing what is there
  copyIn(uri: string, path: string[]): Promise<void>; // may fail part-way
  remove(path: string[]): void; // a file or a folder; nothing if it isn't there
  uri(path: string[]): string;
  freeSpace(): number | null;
}

/** Keep at least this much free after saving a page, so the phone itself keeps working. */
export const LOW_STORAGE_BYTES = 50 * 1024 * 1024;
export const ROOT = "page-drafts";

export class StorageLow extends Error {
  freeBytes: number | null;
  constructor(freeBytes: number | null) {
    super("Your phone is nearly full.");
    this.freeBytes = freeBytes;
  }
}

const noSpace = (e: unknown) => /no space|ENOSPC|disk full|not enough (free )?space|storage full/i.test(String(e));
const PAGE_ID = /^[a-z0-9]{6,40}$/;
const SNIFF: [number[], string][] = [
  [[0xff, 0xd8, 0xff], "image/jpeg"],
  [[0x89, 0x50, 0x4e, 0x47], "image/png"],
  [[0x25, 0x50, 0x44, 0x46], "application/pdf"], // %PDF
];

function sniff(head: Uint8Array): string | null {
  for (const [magic, type] of SNIFF) if (magic.every((b, i) => head[i] === b)) return type;
  return null;
}

function validRecord(x: unknown, id: string): x is Omit<PageDraft, "uri"> {
  const d = x as Partial<PageDraft> | null;
  return (
    !!d &&
    d.id === id &&
    typeof d.name === "string" &&
    typeof d.mimeType === "string" &&
    typeof d.bytes === "number" &&
    typeof d.savedAt === "string"
  );
}

export function createPageDrafts(
  fs: DraftFs,
  scope: (owner: string) => string,
  newId: () => string = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`,
  now: () => Date = () => new Date(),
) {
  const dirFor = (owner: string, attemptId: string) => [ROOT, scope(owner), attemptId];

  /** Replace a small file safely: a failure leaves the old one (or none), never half a file. */
  function replaceText(dir: string[], name: string, text: string): void {
    const tmp = `${name}.tmp`;
    try {
      fs.writeText([...dir, tmp], text);
      fs.rename([...dir, tmp], name);
    } catch (e) {
      fs.remove([...dir, tmp]);
      throw e;
    }
  }

  /** Copy a page in. Throws StorageLow when the phone is (or turns out to be) nearly full, before anything is kept.
   * Once the page itself is in, it stays kept even if writing its record fails: recovery will show it. */
  async function keepPage(owner: string, attemptId: string, source: PageSource): Promise<PageDraft> {
    const bytes = source.size ?? 0;
    const free = fs.freeSpace();
    if (free !== null && free - bytes < LOW_STORAGE_BYTES) throw new StorageLow(free);
    const dir = dirFor(owner, attemptId);
    if (!fs.exists(dir)) fs.makeDir(dir);
    const id = newId();
    const part = `${id}.part`;
    try {
      await fs.copyIn(source.uri, [...dir, part]);
      fs.rename([...dir, part], id);
    } catch (e) {
      fs.remove([...dir, part]);
      if (noSpace(e)) throw new StorageLow(fs.freeSpace());
      throw e;
    }
    const draft: PageDraft = {
      id,
      name: source.name.slice(0, 120),
      mimeType: source.mimeType,
      bytes: fs.size([...dir, id]),
      savedAt: now().toISOString(),
      uri: fs.uri([...dir, id]),
    };
    try {
      const { uri: _uri, ...record } = draft;
      replaceText(dir, `${id}.json`, JSON.stringify(record));
    } catch {
      /* the page is kept; without its record it shows as a recovered page */
    }
    return draft;
  }

  /** Pages kept for this test, oldest first. Never deletes a page. */
  function listPages(owner: string, attemptId: string): PageDraft[] {
    const dir = dirFor(owner, attemptId);
    if (!fs.exists(dir)) return [];
    const names = new Set(fs.list(dir));
    for (const name of names) {
      if (name.endsWith(".part") || name.endsWith(".tmp")) fs.remove([...dir, name]); // interrupted writes
    }
    const out: PageDraft[] = [];
    for (const name of names) {
      if (!PAGE_ID.test(name)) continue;
      const page = [...dir, name];
      let record: Omit<PageDraft, "uri"> | null = null;
      try {
        const parsed: unknown = JSON.parse(fs.readText([...dir, `${name}.json`]));
        if (validRecord(parsed, name)) record = parsed;
      } catch {
        record = null;
      }
      let error: string | undefined;
      try {
        const note = JSON.parse(fs.readText([...dir, `${name}.note.json`])) as { error?: unknown };
        if (typeof note.error === "string") error = note.error;
      } catch {
        error = undefined; // no note, or an unreadable one: only the note is lost
      }
      if (record) {
        out.push({ ...record, uri: fs.uri(page), ...(error ? { error } : {}) });
      } else {
        let head: Uint8Array = new Uint8Array();
        try {
          head = fs.readHead(page, 8);
        } catch {
          /* unreadable now; still listed, so it can be sent or removed */
        }
        out.push({
          id: name,
          name: "Recovered page",
          mimeType: sniff(head) ?? "application/octet-stream",
          bytes: fs.size(page),
          savedAt: now().toISOString(),
          uri: fs.uri(page),
          recovered: true,
          error: error ?? "This page was kept on your phone but its details were lost. Send it again, or remove it.",
        });
      }
    }
    for (const name of names) {
      const base = name.endsWith(".note.json") ? name.slice(0, -10) : name.endsWith(".json") ? name.slice(0, -5) : null;
      if (base && PAGE_ID.test(base) && !names.has(base)) fs.remove([...dir, name]); // a record whose page is gone
    }
    return out.sort((x, y) => x.savedAt.localeCompare(y.savedAt) || x.id.localeCompare(y.id));
  }

  /** Note why an upload failed. Only ever touches the note file: the page and its record are untouched. */
  function notePageError(owner: string, attemptId: string, draft: PageDraft, error: string): void {
    try {
      replaceText(dirFor(owner, attemptId), `${draft.id}.note.json`, JSON.stringify({ error }));
    } catch {
      /* only the note is lost */
    }
  }

  /** The server has the page, or the learner chose to remove it. */
  function removePage(owner: string, attemptId: string, id: string): void {
    const dir = dirFor(owner, attemptId);
    for (const name of [`${id}.json`, `${id}.note.json`, id]) fs.remove([...dir, name]);
  }

  /** The learner chose to remove every page kept for a closed test. */
  function clearAttempt(owner: string, attemptId: string): void {
    fs.remove(dirFor(owner, attemptId));
  }

  /** Sign-out: every kept page of every account on this phone (ISOLATION-01). */
  function clearAll(): void {
    fs.remove([ROOT]);
  }

  return { keepPage, listPages, notePageError, removePage, clearAttempt, clearAll };
}
