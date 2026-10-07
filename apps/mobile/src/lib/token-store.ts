// Native token storage: the app session token is kept only in the OS keystore (Android Keystore / iOS Keychain)
// via expo-secure-store, never in AsyncStorage or logs (roadmap §5.3, P04.S1.T2).
import * as SecureStore from "expo-secure-store";

const KEY = "portal.session";

export const tokenStore = {
  get: () => SecureStore.getItemAsync(KEY),
  set: (token: string) =>
    SecureStore.setItemAsync(KEY, token, { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY }),
  clear: () => SecureStore.deleteItemAsync(KEY),
};
