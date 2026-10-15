// P13.S3.T1/T3 (OFFLINE-PACKS-01; OFFLINE-CORE-01): the offline study pack rules, free of the file system and crypto
// so they run on the host in tests. `study-packs.ts` binds them to expo-file-system and expo-crypto.

/** The newest pack format this build reads (§5.4 rule 6). Raise it only with code that reads the new format. */
export const PACK_FORMAT = 1;

export type PackManifestCore = {
  pack_format_version: number;
  expires_at: string;
  sha256: string;
  includes_premium: boolean;
  files: { asset_version_id: string; sha256: string | null }[];
};

/** Why a downloaded pack can't be kept, or null. Checked before anything is written. */
export function downloadProblem(manifest: PackManifestCore, contentSha256: string, format = PACK_FORMAT): string | null {
  if (manifest.pack_format_version > format) return "This pack needs a newer version of the app.";
  if (contentSha256 !== manifest.sha256) return "The download was damaged. Please try again.";
  return null;
}

/** Why a downloaded file can't be kept, or null. A file the server gave no checksum for is kept as sent. */
export function fileProblem(expected: string | null, actual: string): string | null {
  return expected && expected !== actual ? "A lesson file was damaged in the download. Please try again." : null;
}

/** Whether a stored pack may be opened now: this build reads its format, and it hasn't expired. */
export function usable(manifest: PackManifestCore, now: Date, format = PACK_FORMAT): "ok" | "too_new" | "expired" {
  if (manifest.pack_format_version > format) return "too_new";
  if (new Date(manifest.expires_at) <= now) return "expired";
  return "ok";
}

/**
 * When online, what the server's answer means for a stored pack (P13.S3.T3): removed when it may no longer be kept, or
 * when it holds premium material the plan no longer covers (the preview-only pack can be saved again).
 */
export function afterStatus(
  manifest: PackManifestCore,
  status: { keep: boolean; includes_premium: boolean },
): "kept" | "removed" {
  return !status.keep || (manifest.includes_premium && !status.includes_premium) ? "removed" : "kept";
}
