// Expo web target (development preview only): a random token per browser profile, as a web browser would get.
import * as Crypto from "expo-crypto";

const KEY = "portal.install";

export async function installToken(): Promise<string> {
  try {
    const existing = window.localStorage.getItem(KEY);
    if (existing) return existing;
    const token = Crypto.randomUUID().replaceAll("-", "") + Crypto.randomUUID().replaceAll("-", "");
    window.localStorage.setItem(KEY, token);
    return token;
  } catch {
    return Crypto.randomUUID().replaceAll("-", "").padEnd(32, "0");
  }
}
