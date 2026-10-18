// Expo web target (development preview only): learner preferences in this browser profile's localStorage.
const KEY = "portal-learner-prefs";

export async function readPrefsRaw(): Promise<unknown> {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as unknown) : null;
  } catch {
    return null;
  }
}

export async function writePrefsRaw(value: unknown): Promise<void> {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    // Not remembered; nothing else depends on it.
  }
}
