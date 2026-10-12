"use client";

// P04.S3.T2 (SETTINGS-01): display settings for this device, the account's usual settings, and video quality.
import { useEffect, useState } from "react";
import type { StudySettings } from "@portal/contracts";
import { saveUsualSettings } from "@/app/actions/settings";
import { applyDisplay, fromAccount, type Display, type TextSize, type Theme } from "@/lib/display";

const THEMES: [Theme, string][] = [
  ["system", "Same as this device"],
  ["light", "Light"],
  ["dark", "Dark"],
];
const SIZES: [TextSize, string][] = [
  ["default", "Standard"],
  ["large", "Large"],
  ["larger", "Larger"],
];
const VIDEO: [StudySettings["video_quality"], string][] = [
  ["auto", "Automatic"],
  ["data_saver", "Data saver (lowest)"],
  ["standard", "Standard"],
  ["high", "High"],
];
const small = "rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:border-accent disabled:opacity-60";

/** `current` is this device's display cookie as the server read it (null when the device has none). */
export function StudySettingsForm({ initial, current }: { initial: StudySettings; current: Display | null }) {
  const [usual, setUsual] = useState(initial);
  // A device with its own choice keeps it; one without follows the usual settings (once any are saved).
  const follows = !current?.own && initial.saved;
  const [device, setDevice] = useState<Display>(() => (follows ? fromAccount(initial) : (current ?? fromAccount(initial))));
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (follows) applyDisplay(fromAccount(initial)); // bring this device up to date with the usual settings
  }, [follows, initial]);

  const change = (next: Partial<Display>) => {
    const d = { ...device, ...next, own: true };
    setDevice(d);
    applyDisplay(d);
    setStatus("Changed on this device.");
  };
  const save = async () => {
    setBusy(true);
    const r = await saveUsualSettings({ theme: device.theme, text_size: device.textSize, reduce_motion: device.reduceMotion, data_saver: device.dataSaver });
    setBusy(false);
    if (r.ok) setUsual(r.settings);
    setStatus(r.ok ? "Saved as your usual settings. Your other devices use them unless they have their own." : r.error);
  };
  const follow = () => {
    const d = fromAccount(usual);
    setDevice(d);
    applyDisplay(d);
    setStatus("This device now uses your usual settings.");
  };
  const video = async (quality: StudySettings["video_quality"]) => {
    setBusy(true);
    const r = await saveUsualSettings({ video_quality: quality });
    setBusy(false);
    if (r.ok) setUsual(r.settings);
    setStatus(r.ok ? "Video quality saved." : r.error);
  };

  return (
    <div className="space-y-4 rounded-xl border border-border bg-surface p-4 text-sm">
      <fieldset className="space-y-2">
        <legend className="font-medium">Theme</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {THEMES.map(([v, label]) => (
            <label key={v} className="flex items-center gap-2">
              <input type="radio" name="theme" checked={device.theme === v} onChange={() => change({ theme: v })} />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-2">
        <legend className="font-medium">Text size</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {SIZES.map(([v, label]) => (
            <label key={v} className="flex items-center gap-2">
              <input type="radio" name="text-size" checked={device.textSize === v} onChange={() => change({ textSize: v })} />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-1" checked={device.reduceMotion} onChange={(e) => change({ reduceMotion: e.target.checked })} />
        <span>
          <span className="block font-medium">Reduce motion</span>
          <span className="text-muted">If your device is set to reduce motion, that always applies too.</span>
        </span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-1" checked={device.dataSaver} onChange={(e) => change({ dataSaver: e.target.checked })} />
        <span>
          <span className="block font-medium">Data saver</span>
          <span className="text-muted">Lesson diagrams load only when you tap them.</span>
        </span>
      </label>
      <p className="text-muted">
        {device.own
          ? "This device keeps its own display settings, even when you change them on another device."
          : "This device uses your usual settings."}
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={small} disabled={busy} onClick={save}>
          Save as my usual settings
        </button>
        {device.own && usual.saved && (
          <button type="button" className={small} disabled={busy} onClick={follow}>
            Use my usual settings here
          </button>
        )}
      </div>
      <label className="block space-y-1">
        <span className="block font-medium">Lecture video quality</span>
        <select
          value={usual.video_quality}
          disabled={busy}
          onChange={(e) => video(e.target.value as StudySettings["video_quality"])}
          className="w-full max-w-sm rounded-lg border border-border bg-surface px-3 py-2"
        >
          {VIDEO.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
        <span className="block text-muted">Used on all your devices once lecture videos are available.</span>
      </label>
      <p role="status" className="min-h-5 text-muted">
        {status}
      </p>
    </div>
  );
}
