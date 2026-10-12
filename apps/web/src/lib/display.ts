// P04.S3.T2 (SETTINGS-01): how this device shows the portal: theme, text size, reduced motion and data saver.
//
// The device's own choice always wins on this device. A device that hasn't made one (`own` false) follows the
// account's usual settings, adopted at sign-in and when the account page opens; a change made on another device never
// overwrites a device's own choice. The system's own settings still apply: "system" follows its dark mode, and its
// reduced-motion setting is honoured even when this one is off (globals.css).
//
// Kept in a cookie rather than local storage: it is applied before the first paint by the inline script in the root
// layout, read by the server for data-saver lesson pages, and survives sign-out (which clears site storage on shared
// devices, ISOLATION-01). It holds no personal data.
import type { StudySettings } from "@portal/contracts";

export const DISPLAY_COOKIE = "portal-display";
export const DISPLAY_MAX_AGE_S = 60 * 60 * 24 * 365;

export type Theme = "system" | "light" | "dark";
export type TextSize = "default" | "large" | "larger";
export type Display = { theme: Theme; textSize: TextSize; reduceMotion: boolean; dataSaver: boolean; own: boolean };

const THEMES: Theme[] = ["system", "light", "dark"];
const SIZES: TextSize[] = ["default", "large", "larger"];

/** "dark.large.1.0.1": theme, text size, reduced motion, data saver, the device's own choice. */
export function parseDisplay(raw: string | null | undefined): Display | null {
  const p = (raw ?? "").split(".");
  if (p.length !== 5 || !THEMES.includes(p[0] as Theme) || !SIZES.includes(p[1] as TextSize)) return null;
  return { theme: p[0] as Theme, textSize: p[1] as TextSize, reduceMotion: p[2] === "1", dataSaver: p[3] === "1", own: p[4] === "1" };
}

export function serializeDisplay(d: Display): string {
  return [d.theme, d.textSize, d.reduceMotion ? 1 : 0, d.dataSaver ? 1 : 0, d.own ? 1 : 0].join(".");
}

export function fromAccount(s: Pick<StudySettings, "theme" | "text_size" | "reduce_motion" | "data_saver">): Display {
  return { theme: s.theme, textSize: s.text_size, reduceMotion: s.reduce_motion, dataSaver: s.data_saver, own: false };
}

/** Runs in <head> before the first paint. Mirrors `showDisplay`. */
export const DISPLAY_SCRIPT = `(function(){try{var m=document.cookie.match(/(?:^|; )${DISPLAY_COOKIE}=([^;]*)/);if(!m)return;var p=decodeURIComponent(m[1]).split("."),r=document.documentElement;if(p[0]==="light"||p[0]==="dark")r.dataset.theme=p[0];if(p[1]==="large"||p[1]==="larger")r.dataset.textSize=p[1];if(p[2]==="1")r.dataset.reduceMotion="true";if(p[3]==="1")r.dataset.dataSaver="true";}catch(e){}})();`;

/** Browser only: apply a display choice now and remember it on this device. */
export function applyDisplay(d: Display): void {
  showDisplay(d);
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${DISPLAY_COOKIE}=${serializeDisplay(d)}; Path=/; Max-Age=${DISPLAY_MAX_AGE_S}; SameSite=Lax${secure}`;
}

/** Browser only: this device's display choice, if it has one. */
export function readDisplay(): Display | null {
  const m = document.cookie.match(new RegExp(`(?:^|; )${DISPLAY_COOKIE}=([^;]*)`));
  return parseDisplay(m ? decodeURIComponent(m[1]) : null);
}

/** Browser only: show a display choice on <html> (what DISPLAY_SCRIPT does on a full page load). */
export function showDisplay(d: Display): void {
  const r = document.documentElement;
  if (d.theme === "system") delete r.dataset.theme;
  else r.dataset.theme = d.theme;
  if (d.textSize === "default") delete r.dataset.textSize;
  else r.dataset.textSize = d.textSize;
  if (d.reduceMotion) r.dataset.reduceMotion = "true";
  else delete r.dataset.reduceMotion;
  if (d.dataSaver) r.dataset.dataSaver = "true";
  else delete r.dataset.dataSaver;
}
