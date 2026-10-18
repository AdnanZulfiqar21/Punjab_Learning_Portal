// Expo web target (development preview only): the API address override in this browser profile's localStorage.
import Constants from "expo-constants";

const KEY = "portal-api-origin";
let override: string | null = null;

function variant(): string {
  const v = Constants.expoConfig?.extra?.variant;
  return typeof v === "string" ? v : "development";
}

export function canOverrideApiOrigin(): boolean {
  return variant() !== "production";
}

export function normaliseOrigin(raw: string): string | null {
  const value = raw.trim().replace(/\/+$/, "");
  return /^https?:\/\/[A-Za-z0-9.-]+(:\d{2,5})?$/.test(value) ? value : null;
}

export async function loadApiOriginOverride(): Promise<void> {
  if (!canOverrideApiOrigin()) return;
  try {
    const raw = window.localStorage.getItem(KEY);
    override = raw ? normaliseOrigin(raw) : null;
  } catch {
    override = null;
  }
}

export function apiOriginOverride(): string | null {
  return override;
}

export async function setApiOriginOverride(value: string | null): Promise<void> {
  if (!canOverrideApiOrigin()) return;
  override = value ? normaliseOrigin(value) : null;
  try {
    if (override === null) window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, override);
  } catch {
    // Not remembered; the running app still uses it.
  }
}
