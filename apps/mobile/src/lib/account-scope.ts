// P19.S3.T3 (ISOLATION-01): a short one-way label for an account, so what the app keeps on the device is held apart
// per account and whoever signs in next never sees another person's unsent work. Signing out also deletes it
// (auth.tsx).
export function accountScope(userId: string): string {
  let h = 0x811c9dc5; // FNV-1a, 32-bit
  for (let i = 0; i < userId.length; i++) {
    h ^= userId.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}
