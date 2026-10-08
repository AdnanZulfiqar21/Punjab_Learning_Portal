// An opaque, random per-installation token (roadmap §16.3/16.4). It lets the server recognise *this installation's*
// trial authorization. It is not a device identifier: it is not derived from hardware, and it does not survive a
// reinstall (the server never treats it as reinstall-proof identity). Kept in the OS keystore like the session.
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";

const KEY = "portal.install";
let cached: Promise<string> | null = null;

export function installToken(): Promise<string> {
  cached ??= (async () => {
    const existing = await SecureStore.getItemAsync(KEY);
    if (existing) return existing;
    const token = Crypto.randomUUID().replaceAll("-", "") + Crypto.randomUUID().replaceAll("-", "");
    await SecureStore.setItemAsync(KEY, token, { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
    return token;
  })();
  return cached;
}
