"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { attachCaptions, registerMaster, reviewLecture, saveMarkers, saveTranscript, submitLecture, type LectureResult } from "@/app/actions/lectures";
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

type Upload = { id: string; bytes: number; received: number; state: "uploading" | "processing" | "ready" | "failed"; failure: string | null; chunk_bytes: number };
const TYPES = ["video/mp4", "video/webm", "video/quicktime"];
const mb = (n: number) => `${(n / (1024 * 1024)).toFixed(1)} MB`;

/** MEDIA-UPLOAD-01 (P07.S2.T1): resumable master upload. The server's received count is the resume point, so a dropped
 * connection or a closed tab resumes where the server stopped, not where this device thinks it did. */
export function MasterUpload({ id }: { id: string }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<{ received: number; bytes: number } | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(form: FormData) {
    const f = file;
    if (!f) return;
    if (!TYPES.includes(f.type)) {
      setMessage({ tone: "warn", text: "Choose an MP4, WebM or QuickTime video." });
      return;
    }
    setBusy(true);
    setMessage(null);
    const key = `master-upload:${id}:${f.name}:${f.size}:${f.lastModified}`;
    let up: Upload | null = null;
    try {
      const stored = window.localStorage.getItem(key);
      if (stored) {
        const r = await fetch(`/studio/uploads/${stored}`, { cache: "no-store" });
        const s = r.ok ? ((await r.json()) as Upload) : null;
        if (s?.state === "uploading") up = s;
      }
    } catch {
      /* no device storage: start a new upload */
    }
    if (!up) {
      const sha = String(form.get("sha256") ?? "").trim().toLowerCase();
      const r = await fetch(`/studio/lectures/${id}/master-upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: f.name, bytes: f.size, content_type: f.type, duration_s: Number(form.get("duration_s") ?? 0), ...(sha ? { sha256: sha } : {}) }),
      });
      const body = await r.json().catch(() => null);
      if (!r.ok) {
        setBusy(false);
        setMessage({ tone: "warn", text: body?.detail ?? "Couldn't start the upload." });
        return;
      }
      up = body as Upload;
      try {
        window.localStorage.setItem(key, up.id);
      } catch {
        /* resume on this device won't be available */
      }
    }
    let failures = 0;
    while (up.state === "uploading") {
      setProgress({ received: up.received, bytes: up.bytes });
      const end = Math.min(up.received + up.chunk_bytes, f.size);
      try {
        const r: Response = await fetch(`/studio/uploads/${up.id}?offset=${up.received}`, { method: "PUT", body: f.slice(up.received, end) });
        const body = (await r.json().catch(() => null)) as (Upload & { code_reason?: string; expected_offset?: number; detail?: string }) | null;
        if (r.status === 409 && body?.code_reason === "UPLOAD_OFFSET") {
          up = { ...up, received: Number(body.expected_offset) }; // the server's count wins
          continue;
        }
        if (!r.ok) throw new Error(body?.detail ?? `HTTP ${r.status}`);
        up = body as Upload;
        failures = 0;
      } catch (e) {
        failures += 1;
        if (failures > 4) {
          setBusy(false);
          setMessage({ tone: "warn", text: `The connection dropped (${String(e)}). Press Upload to resume from ${mb(up.received)}; if you reload this page, choose the same file first.` });
          return;
        }
        await new Promise((res) => setTimeout(res, 1000 * 2 ** failures));
      }
    }
    setProgress({ received: up.received, bytes: up.bytes });
    try {
      window.localStorage.removeItem(key);
    } catch {
      /* nothing stored */
    }
    setBusy(false);
    if (up.state === "ready") {
      setMessage({ tone: "ok", text: "Uploaded and checked. It is now this lecture's master; it still needs the independent review." });
      router.refresh();
    } else {
      setMessage({ tone: "warn", text: up.failure ?? "The upload couldn't be used." });
    }
  }

  return (
    // A plain submit handler, not a form action: an action resets the form afterwards, which would clear the chosen
    // file and make resuming after a dropped connection mean choosing it again.
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void upload(new FormData(e.currentTarget));
      }}
      className="space-y-2 rounded-lg border border-border bg-surface p-3 text-sm"
    >
      <p className="font-medium">Upload the master video</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block">Video file (MP4, WebM or QuickTime)</span>
          <input type="file" accept="video/mp4,video/webm,video/quicktime" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="space-y-1">
          <span className="block">Duration (s)</span>
          <input name="duration_s" type="number" min={1} max={7200} required className={`${field} w-28`} />
        </label>
        <label className="space-y-1">
          <span className="block">SHA-256 from the owner (optional)</span>
          <input name="sha256" pattern="[0-9a-fA-F]{64}" className={`${field} w-96 font-mono text-xs`} />
        </label>
        <button type="submit" disabled={busy || !file} className={button}>
          {busy ? "Uploading…" : "Upload"}
        </button>
      </div>
      {progress && (
        <div className="space-y-1">
          <progress value={progress.received} max={progress.bytes} className="w-full" aria-label="Upload progress" />
          <p className="text-muted">
            {mb(progress.received)} of {mb(progress.bytes)}
          </p>
        </div>
      )}
      {message && (
        <p role={message.tone === "warn" ? "alert" : "status"} className={message.tone === "warn" ? "text-danger" : ""}>
          {message.text}
        </p>
      )}
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

type Marker = { scene_id: string; start_s: number; label: string };
const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** MARKERS-01 (P07.S3.T2): chapter markers, one per storyboard scene, timed against the current master video. */
export function MarkersEditor({ id, initial, editable }: { id: string; initial: Marker[]; editable: boolean }) {
  const { busy, result, run } = useRun();
  const [rows, setRows] = useState(initial);
  const [local, setLocal] = useState<string | null>(null);
  return (
    <div className="space-y-3 text-sm">
      <table className="w-full text-left">
        <thead className="text-muted">
          <tr>
            <th scope="col" className="py-1 pr-3 font-medium">
              Scene
            </th>
            <th scope="col" className="py-1 pr-3 font-medium">
              Starts at (s)
            </th>
            <th scope="col" className="py-1 font-medium">
              Chapter title learners see
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.scene_id}>
              <th scope="row" className="py-1 pr-3 font-mono font-normal">
                {r.scene_id}
              </th>
              <td className="py-1 pr-3">
                <input
                  type="number"
                  min={0}
                  max={7200}
                  value={r.start_s}
                  readOnly={!editable || i === 0}
                  aria-label={`Scene ${r.scene_id} start in seconds`}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, start_s: Number(e.target.value) } : x)))}
                  className={`${field} w-24`}
                />{" "}
                <span className="text-muted">{clock(r.start_s)}</span>
              </td>
              <td className="py-1">
                <input
                  value={r.label}
                  maxLength={120}
                  readOnly={!editable}
                  aria-label={`Scene ${r.scene_id} chapter title`}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
                  className={`${field} w-full`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {editable && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            const bad = rows.find((r) => !Number.isInteger(r.start_s) || r.start_s < 0 || r.start_s > 7200 || !r.label.trim());
            if (bad) {
              setLocal(`Scene ${bad.scene_id}: give a whole number of seconds between 0 and 7200, and a chapter title.`);
              return;
            }
            setLocal(null);
            void run(() => saveMarkers(id, rows));
          }}
          className={button}
        >
          {busy ? "Saving…" : "Save chapter markers"}
        </button>
      )}
      {local && (
        <p role="alert" className="text-danger">
          {local}
        </p>
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
