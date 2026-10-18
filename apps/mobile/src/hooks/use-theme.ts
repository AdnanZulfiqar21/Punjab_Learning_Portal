import { createContext, createElement, useContext, useMemo, type ReactNode } from "react";

import { Colors, SubjectAccents, subjectKey, type Palette } from "@/constants/theme";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { useDisplay } from "@/lib/display-context";

/** The colour scheme in use: this device's chosen theme, or the system's while the theme is "system" (SETTINGS-01). */
export function useScheme(): "light" | "dark" {
  const system = useColorScheme();
  const { theme } = useDisplay().display;
  return theme === "system" ? (system === "dark" ? "dark" : "light") : theme;
}

const SubjectContext = createContext<string | null>(null);

/** Inside a subject's screens (a book, chapter or lesson) the accent is that subject's; elsewhere the portal's teal. */
export function SubjectAccent({ subject, children }: { subject: string | null | undefined; children: ReactNode }) {
  return createElement(SubjectContext.Provider, { value: subjectKey(subject) }, children);
}

export function useTheme(): Palette {
  const scheme = useScheme();
  const subject = useContext(SubjectContext);
  return useMemo(() => {
    const base = Colors[scheme];
    const accent = subject ? SubjectAccents[subject]?.[scheme] : null;
    return accent ? { ...base, ...accent } : base;
  }, [scheme, subject]);
}
