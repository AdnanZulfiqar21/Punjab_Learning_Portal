import { useSyncExternalStore } from "react";
import { useColorScheme as useRNColorScheme } from "react-native";

const noopSubscribe = () => () => {};

/** Static web rendering has no colour scheme; use "light" until hydrated on the client, then the real value. */
export function useColorScheme() {
  const hydrated = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
  const colorScheme = useRNColorScheme();
  return hydrated ? colorScheme : "light";
}
