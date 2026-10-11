// P19.S3.T3 (ISOLATION-01): what the portal keeps in this browser (unsent note drafts, unacknowledged practice answers,
// a sealing key, studio drafts, an upload in progress) belongs to whoever was signed in. Signing out of a shared device
// removes all of it, so the next person on the browser starts clean. Client-only.
export function clearDeviceStorage(): void {
  for (const store of ["localStorage", "sessionStorage"] as const) {
    try {
      window[store].clear();
    } catch {
      /* storage unavailable (private mode, blocked): there is nothing kept to clear */
    }
  }
}
