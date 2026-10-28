// Design tokens shared in value with apps/web/src/app/globals.css (P02.S2.T1). Warm neutrals with a teal accent; each
// subject has its own accent (Biology is emerald) used on the subject's cards and inside its lessons. Brand is still
// provisional (B11).
import { Platform } from "react-native";

export const Colors = {
  light: {
    background: "#f8f6f2",
    surface: "#ffffff",
    surfaceMuted: "#f1ede6",
    text: "#1c1a17",
    heading: "#1c1a17",
    muted: "#5b5750",
    border: "#e2ddd4",
    accent: "#0b5d73",
    accentSoft: "#e3f1f5",
    onAccent: "#ffffff",
    warn: "#8a4b00",
    warnSoft: "#fff4e2",
    ok: "#1d6b3a",
    okSoft: "#e7f5ec",
    danger: "#a31d1d",
    dangerSoft: "#fdecec",
    subheading: "#2a5d8f", // headings inside a lesson (owner, 2026-10-27); same value as globals.css --subheading
  },
  dark: {
    background: "#121412",
    surface: "#1b1e1b",
    surfaceMuted: "#242824",
    text: "#ece9e3",
    heading: "#e6d3b3", // dark mode: topic titles in a muted champagne above the white text (owner, 2026-10-28)
    muted: "#aaa69e",
    border: "#333832",
    accent: "#6cc4dc",
    accentSoft: "#143440",
    onAccent: "#121412",
    warn: "#f3b765",
    warnSoft: "#3a2a12",
    ok: "#7fd3a0",
    okSoft: "#13301f",
    danger: "#f19a9a",
    dangerSoft: "#3d1717",
    subheading: "#8fadde", // dark mode: a muted steel blue apart from every subject accent (owner, 2026-10-28)
  },
} as const;

export type Palette = { [K in keyof (typeof Colors)["light"]]: string };

/** Per-subject accents (text contrast ≥ 4.5:1 on the matching surface). Keys are the API's subject codes. */
export const SubjectAccents: Record<string, { light: { accent: string; accentSoft: string }; dark: { accent: string; accentSoft: string } }> = {
  biology: { light: { accent: "#0f7a62", accentSoft: "#e1f3ec" }, dark: { accent: "#7fc9ad", accentSoft: "#123a30" } },
  chemistry: { light: { accent: "#9a4b00", accentSoft: "#fdeee0" }, dark: { accent: "#e3a376", accentSoft: "#3c2410" } },
  physics: { light: { accent: "#3f46b5", accentSoft: "#e8e9fb" }, dark: { accent: "#b4a6ea", accentSoft: "#2a1f50" } },
  mathematics: { light: { accent: "#8a2a6a", accentSoft: "#f9e6f3" }, dark: { accent: "#dca5c6", accentSoft: "#3c1532" } },
  computer_science: { light: { accent: "#0b5d73", accentSoft: "#e3f1f5" }, dark: { accent: "#7cc6cf", accentSoft: "#0f3640" } },
};

/** The subject code for an API subject name or code ("Biology" → "biology"); unknown subjects keep the default accent. */
export function subjectKey(nameOrCode: string | null | undefined): string | null {
  const key = (nameOrCode ?? "").trim().toLowerCase().replace(/\s+/g, "_");
  return key in SubjectAccents ? key : null;
}

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const Radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;

export const Fonts = Platform.select({
  ios: { sans: "system-ui", mono: "ui-monospace" },
  default: { sans: "normal", mono: "monospace" },
  web: { sans: "system-ui, sans-serif", mono: "ui-monospace, monospace" },
});

/** On the web target the native-tabs bar floats at the top of the screen; leave room for it. Native tabs sit at the bottom. */
export const TAB_SCREEN_TOP = Platform.OS === "web" ? 72 : Space.lg;
