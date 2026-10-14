// Expo web target (development preview only): pages are sent straight from the chosen file and never kept in the
// browser. The installed app keeps them in its private storage until they upload (CAPTURE-01).
import type { PageDraft, PageSource } from "@/lib/page-drafts-core";

export { LOW_STORAGE_BYTES, StorageLow, type PageDraft, type PageSource } from "@/lib/page-drafts-core";

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

export function clearAttempt(): void {}

export async function clearPageDrafts(): Promise<void> {}

export async function pickPdf(): Promise<PageSource | null> {
  throw new Error("Choosing a PDF is available in the installed app.");
}
