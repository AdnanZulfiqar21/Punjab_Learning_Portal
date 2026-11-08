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

/** CODE-HIGHLIGHT-01: colours for the parts of a printed program; same values as globals.css `--code-*`. */
export const CodeColors = {
  light: { comment: "#5f636a", keyword: "#7c3aed", constant: "#be185d", number: "#be185d", string: "#166534", function: "#1d4ed8", variable: "#8a4f05" },
  dark: { comment: "#8f9a93", keyword: "#c792ea", constant: "#f78ca8", number: "#f78ca8", string: "#c3e88d", function: "#82aaff", variable: "#ffcb6b" },
} as const;

/** The subject code for an API subject name or code ("Biology" → "biology"); unknown subjects keep the default accent. */
export function subjectKey(nameOrCode: string | null | undefined): string | null {
  const key = (nameOrCode ?? "").trim().toLowerCase().replace(/\s+/g, "_");
  return key in SubjectAccents ? key : null;
}

/** Strong end of each subject's gradient banner (same values as globals.css `--accent-strong`). */
const SubjectStrong: Record<string, { light: string; dark: string }> = {
  biology: { light: "#0b5f4c", dark: "#a6dbc6" },
  chemistry: { light: "#7a3b00", dark: "#ecbe9c" },
  physics: { light: "#323893", dark: "#cdc3f2" },
  mathematics: { light: "#6e2154", dark: "#e8c3d9" },
  computer_science: { light: "#08485a", dark: "#a3d9df" },
};

/** A hex colour mixed with black (`t` of the colour kept), as the web's `color-mix(in oklab, X t%, black)` approximates. */
function towardBlack(hex: string, t: number): string {
  const n = parseInt(hex.slice(1), 16);
  const ch = (shift: number) => Math.round(((n >> shift) & 255) * t).toString(16).padStart(2, "0");
  return `#${ch(16)}${ch(8)}${ch(0)}`;
}

/** PREMIUM-MOBILE-01: the two stops of a subject's banner gradient (web chapter and topic headers): light accent to
 * strong; dark the same, deepened toward black so white text keeps its contrast. */
export function bannerStops(subject: string | null, scheme: "light" | "dark"): [string, string] {
  const key = subject && subject in SubjectAccents ? subject : "computer_science";
  const strong = SubjectStrong[key];
  if (scheme === "light") return [SubjectAccents[key].light.accent, strong.light];
  return [towardBlack(SubjectAccents[key].dark.accent, 0.42), towardBlack(strong.dark, 0.3)];
}

/** PREMIUM-MOBILE-01 (Soft Glass, DESIGN-01): the frosted surface and the gradient mesh behind the browsing screens. Same
 * values as globals.css `--glass-*` and `--mesh-*`. No live blur: a translucent surface over the mesh costs nothing on
 * a low-end phone. */
export const Glass = {
  light: { bg: "rgba(255,255,255,0.72)", border: "rgba(255,255,255,0.9)", shadow: "0px 8px 30px rgba(15,29,43,0.07)", mesh: ["#bfe3ee", "#d9d6f7", "#fbe3cf"] },
  dark: { bg: "rgba(27,30,27,0.72)", border: "rgba(255,255,255,0.08)", shadow: "0px 8px 30px rgba(0,0,0,0.35)", mesh: ["rgba(108,196,220,0.16)", "rgba(120,112,222,0.14)", "rgba(243,183,101,0.1)"] },
} as const;

/** Outfit for headings and the brand (web DESIGN-01); body text keeps the system font. Loaded in the root layout. */
export const HeadingFont = { semibold: "Outfit_600SemiBold", bold: "Outfit_700Bold" } as const;

/** SF Symbol per subject for its icon tile (iOS); other platforms show the subject's initials. */
export const SubjectSymbol: Record<string, { ios: string; initials: string }> = {
  biology: { ios: "leaf.fill", initials: "Bi" },
  chemistry: { ios: "flask.fill", initials: "Ch" },
  physics: { ios: "atom", initials: "Ph" },
  mathematics: { ios: "function", initials: "Ma" },
  computer_science: { ios: "desktopcomputer", initials: "CS" },
};

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const Radius = { sm: 8, md: 12, lg: 16, xl: 22, pill: 999 } as const;

export const Fonts = Platform.select({
  ios: { sans: "system-ui", mono: "ui-monospace" },
  default: { sans: "normal", mono: "monospace" },
  web: { sans: "system-ui, sans-serif", mono: "ui-monospace, monospace" },
});

/** On the web target the native-tabs bar floats at the top of the screen; leave room for it. Native tabs sit at the bottom. */
export const TAB_SCREEN_TOP = Platform.OS === "web" ? 72 : Space.lg;
