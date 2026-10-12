// Expo web target (development preview only): this browser profile's display settings in localStorage.
import type { Display } from "@/lib/display-context";

const KEY = "portal-display-settings";

export async function readDisplay(): Promise<Display | null> {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Display) : null;
  } catch {
    return null;
  }
}

export async function writeDisplay(d: Display): Promise<void> {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(d));
  } catch {
    // Not remembered; nothing else depends on it.
  }
}
