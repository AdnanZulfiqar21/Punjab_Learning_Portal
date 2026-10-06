// Design tokens shared in value with apps/web/src/app/globals.css (P02.S2.T1). Neutral palette until brand (B11).
import { Platform } from "react-native";

export const Colors = {
  light: {
    background: "#f7f8fa",
    surface: "#ffffff",
    surfaceMuted: "#eef1f5",
    text: "#14181f",
    muted: "#4b5563",
    border: "#d9dee6",
    accent: "#0b5d73",
    accentSoft: "#e3f1f5",
    onAccent: "#ffffff",
    warn: "#8a4b00",
    warnSoft: "#fff4e2",
    danger: "#a31d1d",
    dangerSoft: "#fdecec",
  },
  dark: {
    background: "#0f1318",
    surface: "#161b22",
    surfaceMuted: "#1e252e",
    text: "#e8ecf1",
    muted: "#a7b0bc",
    border: "#2c3542",
    accent: "#6cc4dc",
    accentSoft: "#143440",
    onAccent: "#0f1318",
    warn: "#f3b765",
    warnSoft: "#3a2a12",
    danger: "#f19a9a",
    dangerSoft: "#3d1717",
  },
} as const;

export type Palette = (typeof Colors)["light"] | (typeof Colors)["dark"];

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const Radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;

export const Fonts = Platform.select({
  ios: { sans: "system-ui", mono: "ui-monospace" },
  default: { sans: "normal", mono: "monospace" },
  web: { sans: "system-ui, sans-serif", mono: "ui-monospace, monospace" },
});

/** On the web target the native-tabs bar floats at the top of the screen; leave room for it. Native tabs sit at the bottom. */
export const TAB_SCREEN_TOP = Platform.OS === "web" ? 72 : Space.lg;
