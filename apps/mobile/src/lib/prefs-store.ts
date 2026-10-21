// Learner preferences kept on this device (pilot): the Learn tab's class and group, and the reader language. A small
// JSON file in the app's private document directory; no personal data, kept across sign-out like display settings.
import { File, Paths } from "expo-file-system";

const file = () => new File(Paths.document, "learner-prefs.json");

export async function readPrefsRaw(): Promise<unknown> {
  try {
    const f = file();
    return f.exists ? (JSON.parse(await f.text()) as unknown) : null;
  } catch {
    return null;
  }
}

export async function writePrefsRaw(value: unknown): Promise<void> {
  try {
    const f = file();
    if (!f.exists) f.create();
    f.write(JSON.stringify(value));
  } catch {
    // Not remembered after the app closes; nothing else depends on it.
  }
}
