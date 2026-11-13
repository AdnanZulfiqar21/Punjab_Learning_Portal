// SECURITY-HARDEN-01: the one check for a redirect target that came from a request or the API (sign-in's `next`, a
// notification's link). Only a same-site path is kept; anything else becomes `fallback`, so no redirect is open.
// Browsers drop tabs/newlines inside URLs and read "\" as "/", so "/\t/evil" or "/\evil" would become "//evil": any
// control character or backslash is refused outright.
export function safeAppPath(next: unknown, fallback: string): string {
  const n = typeof next === "string" ? next : "";
  if (/[\u0000-\u001f\u007f\\]/.test(n)) return fallback;
  return /^\/(?!\/)/.test(n) ? n : fallback;
}
