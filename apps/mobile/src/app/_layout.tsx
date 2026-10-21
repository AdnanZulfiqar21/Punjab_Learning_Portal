import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useState } from "react";

import { useScheme, useTheme } from "@/hooks/use-theme";
import { VersionGate } from "@/components/version-gate";
import { loadApiOriginOverride } from "@/lib/api-origin";
import { AuthProvider } from "@/lib/auth";
import { DisplayProvider, useReducedMotion } from "@/lib/display";
import { PrefsProvider } from "@/lib/prefs";

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    loadApiOriginOverride().finally(() => {
      setReady(true);
      SplashScreen.hideAsync();
    });
  }, []);
  if (!ready) return null; // the splash screen stays until the API address is known
  return (
    <VersionGate>
    <AuthProvider>
    <DisplayProvider>
    <PrefsProvider>
      <Shell />
    </PrefsProvider>
    </DisplayProvider>
    </AuthProvider>
    </VersionGate>
  );
}

// SETTINGS-01: the chosen theme, and no screen transitions when this device or the system asks for reduced motion.
function Shell() {
  const scheme = useScheme();
  const c = useTheme();
  const still = useReducedMotion();
  const base = scheme === "dark" ? DarkTheme : DefaultTheme;
  return (
    <ThemeProvider
      value={{ ...base, colors: { ...base.colors, background: c.background, card: c.surface, text: c.text, border: c.border, primary: c.accent } }}>
      <Stack screenOptions={{ headerTintColor: c.accent, headerTitleStyle: { color: c.text }, animation: still ? "none" : "default" }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="book/[grade]/[subject]" options={{ title: "Chapters" }} />
        <Stack.Screen name="chapter/[id]" options={{ title: "Chapter" }} />
        <Stack.Screen name="topic/[id]" options={{ title: "Lesson" }} />
        <Stack.Screen name="dashboard" options={{ title: "Dashboard" }} />
        <Stack.Screen name="onboarding" options={{ title: "Learning preferences" }} />
        <Stack.Screen name="attempt/[id]" options={{ title: "Practice test", gestureEnabled: false }} />
        <Stack.Screen name="result/[id]" options={{ title: "Your result" }} />
        <Stack.Screen name="written/[id]" options={{ title: "Written test" }} />
        <Stack.Screen name="help" options={{ title: "Help" }} />
        <Stack.Screen name="notifications" options={{ title: "Notifications" }} />
        <Stack.Screen name="help-article/[slug]" options={{ title: "Help" }} />
        <Stack.Screen name="settings" options={{ title: "Display and data" }} />
      </Stack>
    </ThemeProvider>
  );
}
