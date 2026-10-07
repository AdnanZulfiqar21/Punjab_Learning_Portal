// Expo web target (development preview only; not a shipped surface and not native evidence). The real web product is
// apps/web, which keeps sessions in an HTTP-only cookie. Here the token lives in sessionStorage for the tab's lifetime.
const KEY = "portal.session";

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export const tokenStore = {
  get: async (): Promise<string | null> => storage()?.getItem(KEY) ?? null,
  set: async (token: string): Promise<void> => storage()?.setItem(KEY, token),
  clear: async (): Promise<void> => storage()?.removeItem(KEY),
};
