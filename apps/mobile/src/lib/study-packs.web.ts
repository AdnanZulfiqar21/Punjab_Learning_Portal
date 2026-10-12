// Expo web target (development preview only): offline packs are a feature of the installed app, which keeps them in
// its private storage. The web preview never stores premium content in the browser.
import type { PackContent, StoredPack } from "./study-packs";

export type { PackContent, StoredPack };
export const PACK_FORMAT = 1;

export class PackError extends Error {}

export async function downloadPack(): Promise<StoredPack> {
  throw new PackError("Saving for offline use is available in the installed app.");
}

export function readPack(): StoredPack | null {
  return null;
}

export function packFile(): string | null {
  return null;
}

export function removePack(): void {}

export async function refreshPack(): Promise<"kept" | "removed" | "none"> {
  return "none";
}

export async function clearPacks(): Promise<void> {}
