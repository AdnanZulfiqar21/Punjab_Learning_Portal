// P04.S3.T2 (SETTINGS-01): how this device shows the app: theme, text size, reduced motion and data saver.
//
// The device's own choice always wins on this device. A device that hasn't made one (`own` false) follows the
// account's usual settings, adopted when the learner signs in; a change made on another device never overwrites a
// device's own choice. The system's settings still apply: "system" follows its dark mode, the system text size scales
// on top of this one, and its reduce-motion setting is honoured even when this one is off.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AccessibilityInfo, Appearance } from "react-native";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DEFAULT_DISPLAY, DisplayContext, fromAccount, SCALE, useDisplay, type Ctx, type Display } from "@/lib/display-context";
import { readDisplay, writeDisplay } from "@/lib/display-store";

export { DEFAULT_DISPLAY, fromAccount, useDisplay, type Display, type TextSize, type Theme } from "@/lib/display-context";

export function DisplayProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const [display, setDisplay] = useState<Display>(DEFAULT_DISPLAY);
  const [loaded, setLoaded] = useState(false);
  const token = auth.state.status === "signed_in" ? auth.state.token : null;

  const keep = useCallback((d: Display) => {
    setDisplay(d);
    void writeDisplay(d);
  }, []);

  useEffect(() => {
    readDisplay().then((d) => {
      if (d) setDisplay({ ...DEFAULT_DISPLAY, ...d });
      setLoaded(true);
    });
  }, []);

  // On sign-in, a device without its own choice takes the account's usual settings (once any are saved).
  useEffect(() => {
    if (!loaded || !token || display.own) return;
    let live = true;
    api.settings(token).then(
      (s) => {
        if (live && s.saved) keep(fromAccount(s));
      },
      () => {}, // offline or unavailable: keep what this device has
    );
    return () => {
      live = false;
    };
  }, [loaded, token, display.own, keep]);

  // Native system surfaces (alerts, keyboards) follow the chosen theme too; the web preview has no such call.
  useEffect(() => {
    if (typeof Appearance.setColorScheme === "function") Appearance.setColorScheme(display.theme === "system" ? "unspecified" : display.theme);
  }, [display.theme]);

  const value = useMemo<Ctx>(
    () => ({
      display,
      scale: SCALE[display.textSize] ?? 1,
      change: (next) => keep({ ...display, ...next, own: true }),
      follow: (usual) => keep(fromAccount(usual)),
    }),
    [display, keep],
  );
  return <DisplayContext.Provider value={value}>{children}</DisplayContext.Provider>;
}

/** Reduced motion if this device's setting or the system's asks for it; the system's is never overridden. */
export function useReducedMotion(): boolean {
  const { reduceMotion } = useDisplay().display;
  const [system, setSystem] = useState(false);
  useEffect(() => {
    let live = true;
    AccessibilityInfo.isReduceMotionEnabled().then(
      (on) => live && setSystem(on),
      () => {},
    );
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setSystem);
    return () => {
      live = false;
      sub.remove();
    };
  }, []);
  return reduceMotion || system;
}
