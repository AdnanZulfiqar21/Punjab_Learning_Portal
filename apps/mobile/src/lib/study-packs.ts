// P13.S3.T1-T3 (OFFLINE-PACKS-01): offline study packs, one chapter each, in the app's private document directory and
// filed under the account (ISOLATION-01), so whoever signs in next never sees them; signing out deletes them all.
// A pack is kept only if its SHA-256 and every file's SHA-256 match what the server said; it is opened only if this
// app understands its format; it is dropped when it expires or, when online, the server says it may not be kept.
import * as Crypto from "expo-crypto";
import { Directory, File, Paths } from "expo-file-system";
import type { StudyPack } from "@portal/contracts";

import { accountScope } from "@/lib/account-scope";
import { api, apiUrl } from "@/lib/api";

/** The newest pack format this build reads (§5.4 rule 6). Raise it only with code that reads the new format. */
export const PACK_FORMAT = 1;

export type PackLesson = {
  id: string;
  version: number;
  title: string;
  language: string;
  access_tier: string;
  body: { blocks: { type: string }[] };
  source_refs: { pdf_from: number; pdf_to: number }[];
};
export type PackQuestion = {
  id: string;
  version: number;
  body: {
    stem?: { type: string }[];
    options?: { id: string; blocks?: { type: string }[] }[];
    correct_option_id?: string;
    explanation?: { correct?: { type: string }[]; distractors?: Record<string, string> };
    passage_id?: string;
  };
};
export type PackContent = {
  lessons: PackLesson[];
  questions: PackQuestion[];
  passages: { id: string; version: number; body: { blocks?: { type: string }[] } }[];
};
type Manifest = StudyPack["manifest"] & {
  pack_format_version: number;
  expires_at: string;
  sha256: string;
  bytes: number;
  includes_premium: boolean;
  files: { lesson_id: string; asset_version_id: string; sha256: string | null; url: string }[];
};
export type StoredPack = { manifest: Manifest; content: PackContent; savedAt: string };

const ROOT = "study-packs";
const dirFor = (owner: string) => new Directory(Paths.document, ROOT, accountScope(owner));
const packDir = (owner: string, chapterId: string) => new Directory(dirFor(owner), chapterId);
const hex = (buf: ArrayBuffer) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");

export class PackError extends Error {}

/** Download, verify and store a chapter's pack. Nothing is kept unless every checksum matches. */
export async function downloadPack(token: string, owner: string, chapterId: string): Promise<StoredPack> {
  const pack = await api.studyPack(token, chapterId, PACK_FORMAT);
  const manifest = pack.manifest as Manifest;
  if (manifest.pack_format_version > PACK_FORMAT) throw new PackError("This pack needs a newer version of the app.");
  const digest = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, pack.content);
  if (digest !== manifest.sha256) throw new PackError("The download was damaged. Please try again.");
  const staging = new Directory(dirFor(owner), `${chapterId}.partial`);
  if (staging.exists) staging.delete();
  staging.create({ intermediates: true });
  try {
    const files = new Directory(staging, "files");
    files.create();
    for (const f of manifest.files) {
      const target = new File(files, f.asset_version_id);
      await File.downloadFileAsync(apiUrl(f.url), target, { headers: { Authorization: `Bearer ${token}` }, idempotent: true });
      const sum = hex(await Crypto.digest(Crypto.CryptoDigestAlgorithm.SHA256, new Uint8Array(await target.arrayBuffer())));
      if (f.sha256 && sum !== f.sha256) throw new PackError("A lesson file was damaged in the download. Please try again.");
    }
    const stored: StoredPack = { manifest, content: JSON.parse(pack.content) as PackContent, savedAt: new Date().toISOString() };
    new File(staging, "pack.json").write(JSON.stringify(stored));
    const final = packDir(owner, chapterId);
    if (final.exists) final.delete();
    staging.move(final);
    return stored;
  } catch (e) {
    if (staging.exists) staging.delete(); // never a half-saved pack
    throw e;
  }
}

/** The stored pack, or null when there is none, it is unreadable, its format is too new, or it has expired. */
export function readPack(owner: string, chapterId: string): StoredPack | null {
  try {
    const f = new File(packDir(owner, chapterId), "pack.json");
    if (!f.exists) return null;
    const stored = JSON.parse(f.textSync()) as StoredPack;
    if (stored.manifest.pack_format_version > PACK_FORMAT) return null;
    if (new Date(stored.manifest.expires_at) <= new Date()) {
      removePack(owner, chapterId);
      return null;
    }
    return stored;
  } catch {
    return null;
  }
}

/** Where a packed lesson file lives on the device (or null if it wasn't packed). */
export function packFile(owner: string, chapterId: string, versionId: string): string | null {
  const f = new File(packDir(owner, chapterId), "files", versionId);
  return f.exists ? f.uri : null;
}

export function removePack(owner: string, chapterId: string): void {
  try {
    const d = packDir(owner, chapterId);
    if (d.exists) d.delete();
  } catch {
    /* nothing to remove */
  }
}

/**
 * When online: keep, trim or delete a stored pack as the server says (P13.S3.T3). A pack holding premium lessons or
 * practice is deleted when the plan no longer covers the chapter; the learner can save the preview-only pack again.
 */
export async function refreshPack(token: string, owner: string, chapterId: string): Promise<"kept" | "removed" | "none"> {
  const stored = readPack(owner, chapterId);
  if (!stored) return "none";
  const status = await api.studyPackStatus(token, chapterId);
  if (!status.keep || (stored.manifest.includes_premium && !status.includes_premium)) {
    removePack(owner, chapterId);
    return "removed";
  }
  return "kept";
}

/** Signing out of this device: every account's packs go (ISOLATION-01). */
export async function clearPacks(): Promise<void> {
  try {
    const root = new Directory(Paths.document, ROOT);
    if (root.exists) root.delete();
  } catch {
    /* nothing readable to clear */
  }
}
