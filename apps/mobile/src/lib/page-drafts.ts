// W03.S1.T2 (CAPTURE-01): pages photographed or chosen for a written test are copied into the app's private storage
// first, and only then sent. A page stays on the phone until the server has it, so closing the app, losing signal or
// a failed upload never loses work: it shows as "on this phone, not sent" and can be sent again. Pages are filed
// under the account (ISOLATION-01) and the test, removed once uploaded or when the test is no longer open, and all
// deleted at sign-out. Before keeping a page the free space is checked, so a nearly full phone is said plainly.
import { Directory, File, Paths } from "expo-file-system";

import { accountScope } from "@/lib/account-scope";

export type PageSource = { uri: string; name: string; mimeType: string; size?: number | null };
export type PageDraft = { id: string; name: string; mimeType: string; bytes: number; savedAt: string; uri: string; error?: string };

/** Keep at least this much free after saving a page, so the phone itself keeps working. */
export const LOW_STORAGE_BYTES = 50 * 1024 * 1024;

export class StorageLow extends Error {
  constructor(readonly freeBytes: number | null) {
    super("Your phone is nearly full.");
  }
}

const ROOT = "page-drafts";
const dirFor = (owner: string, attemptId: string) => new Directory(Paths.document, ROOT, accountScope(owner), attemptId);
const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;

/** Free space on the phone in bytes, or null when the system won't say. */
export function freeSpace(): number | null {
  try {
    const free = Paths.availableDiskSpace;
    return Number.isFinite(free) && free >= 0 ? free : null;
  } catch {
    return null;
  }
}

const noSpace = (e: unknown) => /no space|ENOSPC|disk full|not enough (free )?space|storage full/i.test(String(e));

/** Copy a page into private storage. Throws StorageLow when the phone is (or turns out to be) nearly full. */
export async function keepPage(owner: string, attemptId: string, source: PageSource): Promise<PageDraft> {
  const from = new File(source.uri);
  const bytes = source.size ?? from.size ?? 0;
  const free = freeSpace();
  if (free !== null && free - bytes < LOW_STORAGE_BYTES) throw new StorageLow(free);
  const dir = dirFor(owner, attemptId);
  if (!dir.exists) dir.create({ intermediates: true });
  const id = newId();
  const target = new File(dir, id);
  try {
    await from.copy(target);
  } catch (e) {
    if (target.exists) target.delete();
    if (noSpace(e)) throw new StorageLow(freeSpace());
    throw e;
  }
  const draft: PageDraft = {
    id,
    name: source.name.slice(0, 120),
    mimeType: source.mimeType,
    bytes: target.size,
    savedAt: new Date().toISOString(),
    uri: target.uri,
  };
  try {
    new File(dir, `${id}.json`).write(JSON.stringify(draft)); // the page counts as kept only once this is written
  } catch (e) {
    if (target.exists) target.delete();
    throw noSpace(e) ? new StorageLow(freeSpace()) : e;
  }
  return draft;
}

/** Pages kept for this test, oldest first. A copy without its record (an interrupted save) is tidied away. */
export function listPages(owner: string, attemptId: string): PageDraft[] {
  try {
    const dir = dirFor(owner, attemptId);
    if (!dir.exists) return [];
    const out: PageDraft[] = [];
    const names = new Set(dir.list().map((e) => e.name));
    for (const entry of dir.list()) {
      if (!(entry instanceof File)) continue;
      if (entry.name.endsWith(".json")) {
        try {
          const d = JSON.parse(entry.textSync()) as PageDraft;
          if (names.has(d.id)) out.push({ ...d, uri: new File(dir, d.id).uri });
          else entry.delete();
        } catch {
          entry.delete();
        }
      } else if (!names.has(`${entry.name}.json`)) {
        entry.delete();
      }
    }
    return out.sort((x, y) => x.savedAt.localeCompare(y.savedAt));
  } catch {
    return [];
  }
}

export function notePageError(owner: string, attemptId: string, draft: PageDraft, error: string): void {
  try {
    new File(dirFor(owner, attemptId), `${draft.id}.json`).write(JSON.stringify({ ...draft, error }));
  } catch {
    /* the page itself is still kept; only the note is lost */
  }
}

export function removePage(owner: string, attemptId: string, id: string): void {
  try {
    const dir = dirFor(owner, attemptId);
    for (const name of [id, `${id}.json`]) {
      const f = new File(dir, name);
      if (f.exists) f.delete();
    }
  } catch {
    /* nothing to remove */
  }
}

/** The test is no longer open: what is still on the phone can't be sent, so it isn't kept. */
export function clearAttempt(owner: string, attemptId: string): number {
  try {
    const dir = dirFor(owner, attemptId);
    if (!dir.exists) return 0;
    const n = dir.list().filter((e) => e.name.endsWith(".json")).length;
    dir.delete();
    return n;
  } catch {
    return 0;
  }
}

/** Sign-out: every kept page of every account on this phone (ISOLATION-01). */
export async function clearPageDrafts(): Promise<void> {
  try {
    const root = new Directory(Paths.document, ROOT);
    if (root.exists) root.delete();
  } catch {
    /* nothing kept */
  }
}

/** Choose a PDF with the system document picker (W03.S1.T2 document import). Null when cancelled. */
export async function pickPdf(): Promise<PageSource | null> {
  const picked = await File.pickFileAsync({ mimeTypes: ["application/pdf"] });
  if (picked.canceled) return null;
  const f = picked.result;
  return { uri: f.uri, name: f.name || "document.pdf", mimeType: f.type || "application/pdf", size: f.size };
}
