// Expo web target (development preview only): note drafts live in localStorage for this browser profile.
import { accountScope } from "@/lib/account-scope";
import type { NoteDraft } from "./note-drafts";

export type { NoteDraft };
const PREFIX = "note-draft:";
const key = (owner: string, lessonId: string) => `${PREFIX}${accountScope(owner)}:${lessonId}`;

export async function readDraft(owner: string, lessonId: string): Promise<NoteDraft | null> {
  try {
    const raw = window.localStorage.getItem(key(owner, lessonId));
    return raw ? (JSON.parse(raw) as NoteDraft) : null;
  } catch {
    return null;
  }
}

export async function writeDraft(owner: string, lessonId: string, draft: NoteDraft | null): Promise<void> {
  try {
    if (draft) window.localStorage.setItem(key(owner, lessonId), JSON.stringify(draft));
    else window.localStorage.removeItem(key(owner, lessonId));
  } catch {
    /* storage unavailable */
  }
}

export async function clearDrafts(): Promise<void> {
  try {
    for (const k of Object.keys(window.localStorage)) if (k.startsWith(PREFIX)) window.localStorage.removeItem(k);
  } catch {
    /* storage unavailable */
  }
}
