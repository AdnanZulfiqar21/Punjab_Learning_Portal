// SETTINGS-01: this device's display settings, in a small JSON file in the app's private document directory. They are
// about the device, hold no personal data and are kept across sign-out.
import { File, Paths } from "expo-file-system";

import type { Display } from "@/lib/display-context";

const file = () => new File(Paths.document, "display-settings.json");

export async function readDisplay(): Promise<Display | null> {
  try {
    const f = file();
    return f.exists ? (JSON.parse(await f.text()) as Display) : null;
  } catch {
    return null;
  }
}

export async function writeDisplay(d: Display): Promise<void> {
  try {
    const f = file();
    if (!f.exists) f.create();
    f.write(JSON.stringify(d));
  } catch {
    // A failed write only means the choice isn't remembered after the app closes.
  }
}
