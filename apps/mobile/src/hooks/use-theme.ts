import { Colors, type Palette } from "@/constants/theme";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { useDisplay } from "@/lib/display-context";

/** The colour scheme in use: this device's chosen theme, or the system's while the theme is "system" (SETTINGS-01). */
export function useScheme(): "light" | "dark" {
  const system = useColorScheme();
  const { theme } = useDisplay().display;
  return theme === "system" ? (system === "dark" ? "dark" : "light") : theme;
}

export function useTheme(): Palette {
  return Colors[useScheme()];
}
