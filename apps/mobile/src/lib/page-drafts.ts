// W03.S1.T2 (CAPTURE-01): pages photographed or chosen for a written test are copied into the app's private storage
// first, and only then sent, so closing the app, losing signal or a failed upload never loses work. Pages are filed
// under the account (ISOLATION-01) and the test, and removed once uploaded, when the learner removes them, or at
// sign-out. The storage rules (and their fault handling, OCT14-04) are in page-drafts-core.ts; this binds them to
// expo-file-system.
import { Directory, File, Paths } from "expo-file-system";

import { accountScope } from "@/lib/account-scope";
import { createPageDrafts, type DraftFs, type PageSource } from "@/lib/page-drafts-core";

export { LOW_STORAGE_BYTES, StorageLow, type PageDraft, type PageSource } from "@/lib/page-drafts-core";

const file = (path: string[]) => new File(Paths.document, ...path);
const dir = (path: string[]) => new Directory(Paths.document, ...path);

const expoFs: DraftFs = {
  exists: (path) => dir(path).exists || file(path).exists,
  makeDir: (path) => dir(path).create({ intermediates: true, idempotent: true }),
  list: (path) => dir(path).list().filter((e) => e instanceof File).map((e) => e.name),
  readText: (path) => file(path).textSync(),
  readHead: (path, bytes) => {
    const handle = file(path).open();
    try {
      return handle.readBytes(bytes);
    } finally {
      handle.close();
    }
  },
  size: (path) => file(path).size ?? 0,
  writeText: (path, text) => file(path).write(text),
  rename: (path, newName) => {
    const target = file([...path.slice(0, -1), newName]);
    if (target.exists) target.delete();
    file(path).rename(newName);
  },
  copyIn: async (uri, path) => {
    await new File(uri).copy(file(path));
  },
  remove: (path) => {
    const d = dir(path);
    if (d.exists) d.delete();
    else {
      const f = file(path);
      if (f.exists) f.delete();
    }
  },
  uri: (path) => file(path).uri,
  freeSpace: () => {
    try {
      const free = Paths.availableDiskSpace;
      return Number.isFinite(free) && free >= 0 ? free : null;
    } catch {
      return null;
    }
  },
};

const drafts = createPageDrafts(expoFs, accountScope);

export const keepPage = drafts.keepPage;
export const listPages = drafts.listPages;
export const notePageError = drafts.notePageError;
export const removePage = drafts.removePage;
export const clearAttempt = drafts.clearAttempt;

export async function clearPageDrafts(): Promise<void> {
  try {
    drafts.clearAll();
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
