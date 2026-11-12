import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { Outfit_600SemiBold, Outfit_700Bold, useFonts } from "@expo-google-fonts/outfit";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useState } from "react";

import { HeadingFont } from "@/constants/theme";
import { useScheme, useTheme } from "@/hooks/use-theme";
import { VersionGate } from "@/components/version-gate";
import { loadApiOriginOverride } from "@/lib/api-origin";
import { AuthProvider } from "@/lib/auth";
import { DisplayProvider, useReducedMotion } from "@/lib/display";
import { PrefsProvider } from "@/lib/prefs";

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  // PREMIUM-MOBILE-01: the heading font ships inside the app; a failed load falls back to the system font.
  const [fontsLoaded, fontError] = useFonts({ Outfit_600SemiBold, Outfit_700Bold });
  const fontsDone = fontsLoaded || !!fontError;
  useEffect(() => {
    loadApiOriginOverride().finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (ready && fontsDone) SplashScreen.hideAsync();
  }, [ready, fontsDone]);
  if (!ready || !fontsDone) return null; // the splash screen stays until the API address and the fonts are known
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
      {/* PREMIUM-MOBILE-01: a quiet header on the page colour (no rule under it), the title in Outfit, and only the back
          chevron, so a long title or "(tabs)" never fills the back button. */}
      <Stack
        screenOptions={{
          headerTintColor: c.accent,
          headerTitleStyle: { color: c.text, fontFamily: HeadingFont.semibold, fontSize: 17 },
          headerStyle: { backgroundColor: c.background },
          headerShadowVisible: false,
          headerBackButtonDisplayMode: "minimal",
          animation: still ? "none" : "default",
        }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false, title: "Learn" }} />
        <Stack.Screen name="book/[grade]/[subject]" options={{ title: "Chapters" }} />
        <Stack.Screen name="chapter/[id]" options={{ title: "Chapter" }} />
        <Stack.Screen name="topic/[id]" options={{ title: "Lesson" }} />
        <Stack.Screen name="exercises" options={{ title: "Book exercises" }} />
        <Stack.Screen name="chapter-practice" options={{ title: "Chapter practice" }} />
        <Stack.Screen name="chapter-mocks" options={{ title: "Chapter mock tests" }} />
        <Stack.Screen name="book-mocks" options={{ title: "Book Mock Test" }} />
        <Stack.Screen name="mock-paper" options={{ title: "Mock test" }} />
        <Stack.Screen name="exercise/[id]" options={{ title: "Exercise" }} />
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
