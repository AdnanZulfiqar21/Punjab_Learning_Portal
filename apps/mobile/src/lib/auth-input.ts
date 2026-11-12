// AUTH-PASSWORD-01 / AUTH-PREMIUM-01: small checks used by the sign-in, sign-up and forgotten-password screens.
// Plain functions (no React Native imports) so they run in the host-side unit tests.

/** "14/05/2008", "14-05-2008" or "14.05.2008" → "2008-05-14"; null when it isn't a real date. */
export function isoDate(typed: string): string | null {
  const m = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(typed.trim());
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== mo - 1 || date.getUTCDate() !== d) return null;
  return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** A rough guide, 0 (empty) to 4; the only rule the server keeps is at least 10 characters. Same as the web. */
export function passwordStrength(value: string): 0 | 1 | 2 | 3 | 4 {
  if (!value) return 0;
  let s = 0;
  if (value.length >= 10) s++;
  if (value.length >= 14) s++;
  if (/[A-Z]/.test(value) && /[a-z]/.test(value)) s++;
  if (/\d|[^\w]/.test(value)) s++;
  return Math.max(1, s) as 1 | 2 | 3 | 4;
}

export const STRENGTH_LABEL = ["", "Too weak", "Okay", "Good", "Strong"] as const;

/** A plausible email address, enough to catch a typo before asking the server. */
export function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
