// Expo web target (development preview only): note drafts live in localStorage for this browser profile.
import type { NoteDraft } from "./note-drafts";

export type { NoteDraft };
const key = (lessonId: string) => `note-draft:${lessonId}`;

export async function readDraft(lessonId: string): Promise<NoteDraft | null> {
  try {
    const raw = window.localStorage.getItem(key(lessonId));
    return raw ? (JSON.parse(raw) as NoteDraft) : null;
  } catch {
    return null;
  }
}

export async function writeDraft(lessonId: string, draft: NoteDraft | null): Promise<void> {
  try {
    if (draft) window.localStorage.setItem(key(lessonId), JSON.stringify(draft));
    else window.localStorage.removeItem(key(lessonId));
  } catch {
    /* storage unavailable */
  }
}
