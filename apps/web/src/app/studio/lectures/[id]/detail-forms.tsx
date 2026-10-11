"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { attachCaptions, registerMaster, reviewLecture, saveTranscript, submitLecture, type LectureResult } from "@/app/actions/lectures";
import { CHECKS, LANGUAGE } from "../labels";
import { Problems } from "../lecture-forms";

const field = "rounded-lg border border-border bg-surface px-3 py-2";
const button = "rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

function useRun() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<LectureResult | null>(null);
  async function run(fn: () => Promise<LectureResult>) {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    setResult(r);
    if (r.ok) router.refresh();
  }
  return { busy, result, run };
}

export function MasterForm({ id }: { id: string }) {
  const { busy, result, run } = useRun();
  return (
    <form action={(f) => run(() => registerMaster(id, f))} className="flex flex-wrap items-end gap-3 text-sm">
      <label className="space-y-1">
        <span className="block">File name</span>
        <input name="filename" required minLength={3} maxLength={255} className={field} />
      </label>
      <label className="space-y-1">
        <span className="block">SHA-256</span>
        <input name="sha256" required pattern="[0-9a-fA-F]{64}" className={`${field} w-96 font-mono text-xs`} />
      </label>
      <label className="space-y-1">
        <span className="block">Size (bytes)</span>
        <input name="bytes" type="number" min={1} required className={`${field} w-36`} />
      </label>
      <label className="space-y-1">
        <span className="block">Duration (s)</span>
        <input name="duration_s" type="number" min={1} max={7200} required className={`${field} w-28`} />
      </label>
      <label className="space-y-1">
        <span className="block">Where it is kept</span>
        <input name="location" required minLength={3} maxLength={500} className={field} />
      </label>
      <button type="submit" disabled={busy} className={button}>
        {busy ? "Saving…" : "Register master"}
      </button>
      <Problems result={result} />
    </form>
  );
}

export function CaptionsForm({ id, language }: { id: string; language: string }) {
  const { busy, result, run } = useRun();
  return (
    <form action={(f) => run(() => attachCaptions(id, f))} className="flex flex-wrap items-end gap-3 text-sm">
      <label className="space-y-1">
        <span className="block">Language</span>
        <select name="language" defaultValue={language} className={field}>
          {Object.entries(LANGUAGE).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1">
        <span className="block">Captions version ID (Studio → Assets, WebVTT)</span>
        <input name="asset_version_id" required pattern="[0-9a-fA-F-]{36}" className={`${field} w-96 font-mono text-xs`} />
      </label>
      <button type="submit" disabled={busy} className={button}>
        {busy ? "Attaching…" : "Attach captions"}
      </button>
      <Problems result={result} />
    </form>
  );
}

export function TranscriptEditor({ id, scenes, editable }: { id: string; scenes: { scene_id: string; text: string }[]; editable: boolean }) {
  const { busy, result, run } = useRun();
  const [rows, setRows] = useState(scenes);
  return (
    <div className="space-y-3 text-sm">
      {rows.map((r, i) => (
        <label key={r.scene_id} className="block space-y-1">
          <span className="block font-medium">Scene {r.scene_id}</span>
          <textarea
            value={r.text}
            readOnly={!editable}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
            rows={3}
            maxLength={4000}
            className={`${field} w-full`}
          />
        </label>
      ))}
      {editable && (
        <button type="button" disabled={busy} onClick={() => run(() => saveTranscript(id, rows))} className={button}>
          {busy ? "Saving…" : "Save transcript"}
        </button>
      )}
      <Problems result={result} />
    </div>
  );
}

export function SubmitLecture({ id, ready }: { id: string; ready: boolean }) {
  const { busy, result, run } = useRun();
  return (
    <div className="space-y-2">
      <button type="button" disabled={busy || !ready} onClick={() => run(() => submitLecture(id))} className={button}>
        {busy ? "Submitting…" : "Submit for academic review"}
      </button>
      <Problems result={result} />
    </div>
  );
}

export function ReviewForm({ id }: { id: string }) {
  const { busy, result, run } = useRun();
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [notes, setNotes] = useState("");
  const all = CHECKS.every(([k]) => checks[k]);
  return (
    <section aria-labelledby="do-review-h" className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
      <h2 id="do-review-h" className="text-lg font-semibold">
        Academic review
      </h2>
      <p className="text-muted">Watch the whole lecture against the storyboard and the textbook pages. Approval needs every check.</p>
      <fieldset className="space-y-1">
        <legend className="sr-only">Checks</legend>
        {CHECKS.map(([k, label]) => (
          <label key={k} className="flex items-center gap-2">
            <input type="checkbox" checked={!!checks[k]} onChange={(e) => setChecks({ ...checks, [k]: e.target.checked })} /> {label}
          </label>
        ))}
      </fieldset>
      <label className="block space-y-1">
        <span className="block font-medium">Notes: scientific terms, Roman Urdu spellings, pronunciation, equations, timing</span>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={4} maxLength={4000} className={`${field} w-full`} />
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="button" disabled={busy || !all || notes.trim().length < 10} onClick={() => run(() => reviewLecture(id, "approve", checks, notes))} className={button}>
          Approve
        </button>
        <button
          type="button"
          disabled={busy || notes.trim().length < 10}
          onClick={() => run(() => reviewLecture(id, "request_changes", checks, notes))}
          className="rounded-lg border border-border px-4 py-2 font-medium hover:border-accent disabled:opacity-60"
        >
          Request changes
        </button>
      </div>
      <Problems result={result} />
    </section>
  );
}
