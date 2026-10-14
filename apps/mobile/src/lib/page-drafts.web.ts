// Expo web target (development preview only): pages are sent straight from the chosen file and never kept in the
// browser. The installed app keeps them in its private storage until they upload (CAPTURE-01).
import type { PageDraft, PageSource } from "./page-drafts";

export type { PageDraft, PageSource };
export const LOW_STORAGE_BYTES = 50 * 1024 * 1024;

export class StorageLow extends Error {
  constructor(readonly freeBytes: number | null) {
    super("Your phone is nearly full.");
  }
}

export function freeSpace(): number | null {
  return null;
}

export async function keepPage(_owner: string, _attemptId: string, source: PageSource): Promise<PageDraft> {
  return {
    id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`,
    name: source.name,
    mimeType: source.mimeType,
    bytes: source.size ?? 0,
    savedAt: new Date().toISOString(),
    uri: source.uri,
  };
}

export function listPages(): PageDraft[] {
  return [];
}

export function notePageError(): void {}

export function removePage(): void {}

export function clearAttempt(): number {
  return 0;
}

export async function clearPageDrafts(): Promise<void> {}

export async function pickPdf(): Promise<PageSource | null> {
  throw new Error("Choosing a PDF is available in the installed app.");
}
