// Unsent lesson-note drafts (STUDY-TOOLS-01): a small JSON file per lesson in the app's private document directory, so
// a note written offline survives the app closing. Cleared once the server confirms the note.
import { File, Paths } from "expo-file-system";

export type NoteDraft = { text: string; base: number };
const fileFor = (lessonId: string) => new File(Paths.document, `note-draft-${lessonId}.json`);

export async function readDraft(lessonId: string): Promise<NoteDraft | null> {
  try {
    const f = fileFor(lessonId);
    return f.exists ? (JSON.parse(await f.text()) as NoteDraft) : null;
  } catch {
    return null;
  }
}

export async function writeDraft(lessonId: string, draft: NoteDraft | null): Promise<void> {
  try {
    const f = fileFor(lessonId);
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
