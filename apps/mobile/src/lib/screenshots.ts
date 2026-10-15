// P15.S3.T1 (MOBILE-SCREENSHOTS-01): what a help request accepts as a screenshot, checked on the phone before sending
// (the server checks again and re-encodes it in isolation). Kept in step with `MAX_SCREENSHOT_BYTES` in the API.
export const MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024;
const TYPES = new Set(["image/jpeg", "image/jpg", "image/png"]);

/** Why this picture can't be added, or null. Unknown type or size is left to the server to judge. */
export function screenshotProblem(asset: { mimeType?: string | null; fileSize?: number | null }): string | null {
  const type = asset.mimeType?.toLowerCase();
  if (type && !TYPES.has(type)) return "Screenshots must be JPEG or PNG pictures.";
  if (asset.fileSize && asset.fileSize > MAX_SCREENSHOT_BYTES) return "Screenshots can be at most 5 MB.";
  return null;
}
