// P04.S3.T2 (SETTINGS-01): this device's display settings as React context. Kept free of API and auth imports so
// basic UI pieces (text, theme) can read it without import cycles; the provider lives in lib/display.tsx.
import { createContext, useContext } from "react";
import type { StudySettings } from "@portal/contracts";

export type Theme = "system" | "light" | "dark";
export type TextSize = "default" | "large" | "larger";
export type Display = { theme: Theme; textSize: TextSize; reduceMotion: boolean; dataSaver: boolean; own: boolean };

export const DEFAULT_DISPLAY: Display = { theme: "system", textSize: "default", reduceMotion: false, dataSaver: false, own: false };
export const SCALE: Record<TextSize, number> = { default: 1, large: 1.125, larger: 1.25 };

export function fromAccount(s: Pick<StudySettings, "theme" | "text_size" | "reduce_motion" | "data_saver">): Display {
  return { theme: s.theme, textSize: s.text_size, reduceMotion: s.reduce_motion, dataSaver: s.data_saver, own: false };
}

export type Ctx = { display: Display; scale: number; change: (next: Partial<Display>) => void; follow: (usual: StudySettings) => void };
export const DisplayContext = createContext<Ctx>({ display: DEFAULT_DISPLAY, scale: 1, change: () => {}, follow: () => {} });

export function useDisplay(): Ctx {
  return useContext(DisplayContext);
}
