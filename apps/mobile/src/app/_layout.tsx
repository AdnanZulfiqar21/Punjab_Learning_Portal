import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";

import { useColorScheme } from "@/hooks/use-color-scheme";
import { useTheme } from "@/hooks/use-theme";
import { AuthProvider } from "@/lib/auth";

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const scheme = useColorScheme();
  const c = useTheme();
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);
  const base = scheme === "dark" ? DarkTheme : DefaultTheme;
  return (
    <AuthProvider>
    <ThemeProvider
      value={{ ...base, colors: { ...base.colors, background: c.background, card: c.surface, text: c.text, border: c.border, primary: c.accent } }}>
      <Stack screenOptions={{ headerTintColor: c.accent, headerTitleStyle: { color: c.text } }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="book/[grade]/[subject]" options={{ title: "Chapters" }} />
        <Stack.Screen name="chapter/[id]" options={{ title: "Chapter" }} />
        <Stack.Screen name="onboarding" options={{ title: "Learning preferences" }} />
      </Stack>
    </ThemeProvider>
    </AuthProvider>
  );
}
