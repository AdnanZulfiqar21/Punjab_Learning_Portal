// Unsent lesson-note drafts (STUDY-TOOLS-01): a small JSON file per lesson in the app's private document directory, so
// a note written offline survives the app closing. Cleared once the server confirms the note. ISOLATION-01: each draft
// is filed under its account, and signing out deletes them all.
import { Directory, File, Paths } from "expo-file-system";

import { accountScope } from "@/lib/account-scope";

export type NoteDraft = { text: string; base: number };
const PREFIX = "note-draft-";
const fileFor = (owner: string, lessonId: string) => new File(Paths.document, `${PREFIX}${accountScope(owner)}-${lessonId}.json`);

export async function readDraft(owner: string, lessonId: string): Promise<NoteDraft | null> {
  try {
    const f = fileFor(owner, lessonId);
    return f.exists ? (JSON.parse(await f.text()) as NoteDraft) : null;
  } catch {
    return null;
  }
}

export async function writeDraft(owner: string, lessonId: string, draft: NoteDraft | null): Promise<void> {
  try {
    const f = fileFor(owner, lessonId);
    if (!draft) {
      if (f.exists) f.delete();
      return;
    }
    if (!f.exists) f.create();
    f.write(JSON.stringify(draft));
  } catch {
    /* storage failure: the note still saves; it just isn't kept if the app closes while offline */
  }
}

/** Signing out of this device: every account's unsent drafts go. */
export async function clearDrafts(): Promise<void> {
  try {
    for (const entry of new Directory(Paths.document).list()) {
      if (entry instanceof File && entry.name.startsWith(PREFIX)) entry.delete();
    }
  } catch {
    /* nothing readable to clear */
  }
}
