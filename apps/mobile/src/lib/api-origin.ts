// Preview and development builds only: the API address can be changed on the device, because the laptop's Wi-Fi
// address changes between networks and a new signed build for every change is not workable. A production build
// never reads this; its origin is the one baked in at build time (app.config.ts).
import Constants from "expo-constants";
import { File, Paths } from "expo-file-system";

let override: string | null = null;
let loaded = false;

const file = () => new File(Paths.document, "api-origin.json");

function variant(): string {
  const v = Constants.expoConfig?.extra?.variant;
  return typeof v === "string" ? v : "development";
}

export function canOverrideApiOrigin(): boolean {
  return variant() !== "production";
}

/** `http://host:port`, no path; anything else is refused. */
export function normaliseOrigin(raw: string): string | null {
  const value = raw.trim().replace(/\/+$/, "");
  return /^https?:\/\/[A-Za-z0-9.-]+(:\d{2,5})?$/.test(value) ? value : null;
}

export async function loadApiOriginOverride(): Promise<void> {
  if (loaded) return;
  loaded = true;
  if (!canOverrideApiOrigin()) return;
  try {
    const f = file();
    if (f.exists) {
      const parsed = JSON.parse(await f.text()) as { origin?: unknown };
      override = typeof parsed.origin === "string" ? normaliseOrigin(parsed.origin) : null;
    }
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
    const f = file();
    if (override === null) {
      if (f.exists) f.delete();
    } else {
      if (!f.exists) f.create();
      f.write(JSON.stringify({ origin: override }));
    }
  } catch {
    // Not remembered after the app closes; the running app still uses it.
  }
}
