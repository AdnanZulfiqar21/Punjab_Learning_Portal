"use client";

import { useState, useTransition } from "react";
import { setPublicationRights } from "@/app/actions/sources";
import { decideNotice, logNotice, reviewSource } from "@/app/actions/updates";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const btn = "rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent disabled:opacity-60";

function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const run = (fn: () => Promise<{ ok: boolean; error?: string }>, onOk?: () => void) =>
    start(async () => {
      setError(null);
      const out = await fn();
      if (out.ok) onOk?.();
      else setError(out.error ?? "Something went wrong.");
    });
  return { error, pending, run };
}

export function ReviewSourceButton({ id, label }: { id: string; label: string }) {
  const [note, setNote] = useState("");
  const { error, pending, run } = useAction();
  return (
    <div className="space-y-1">
      <label className="block text-xs text-muted" htmlFor={`note-${id}`}>
        Review note for {label}
      </label>
      <div className="flex gap-2">
        <input id={`note-${id}`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} className={field} />
        <button type="button" className={btn} disabled={pending || note.trim().length < 10} onClick={() => run(() => reviewSource(id, note.trim()), () => setNote(""))}>
          Mark reviewed
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function LogNoticeForm() {
  const [v, setV] = useState({ grade: "11", subject: "biology", title: "", source_url: "", summary: "" });
  const { error, pending, run } = useAction();
  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface p-4">
      <h3 className="font-medium">Log an official notice</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        <select aria-label="Notice class" value={v.grade} onChange={(e) => setV({ ...v, grade: e.target.value })} className={field}>
          <option value="11">Class 11</option>
          <option value="12">Class 12</option>
        </select>
        <select aria-label="Notice subject" value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value })} className={field}>
          {["biology", "chemistry", "physics", "computer_science", "mathematics"].map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
      </div>
      <input aria-label="Notice title" placeholder="Title" value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} maxLength={200} className={field} />
      <input aria-label="Notice link" placeholder="Official link (https://…)" value={v.source_url} onChange={(e) => setV({ ...v, source_url: e.target.value })} className={field} />
      <textarea aria-label="Notice summary" placeholder="What changed, according to the notice" value={v.summary} onChange={(e) => setV({ ...v, summary: e.target.value })} rows={3} className={field} />
      <button
        type="button"
        className={btn}
        disabled={pending || v.title.trim().length < 5 || v.summary.trim().length < 10}
        onClick={() =>
          run(
            () => logNotice({ grade: Number(v.grade), subject: v.subject, title: v.title.trim(), source_url: v.source_url.trim() || null, summary: v.summary.trim() }),
            () => setV({ ...v, title: "", source_url: "", summary: "" }),
          )
        }
      >
        Log notice for review
      </button>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function DecideNotice({ id }: { id: string }) {
  const [decision, setDecision] = useState("");
  const { error, pending, run } = useAction();
  return (
    <div className="space-y-1">
      <textarea aria-label="Decision" placeholder="Decision and what needs to change" value={decision} onChange={(e) => setDecision(e.target.value)} rows={2} className={field} />
      <div className="flex gap-2">
        <button type="button" className={btn} disabled={pending || decision.trim().length < 10} onClick={() => run(() => decideNotice(id, true, decision.trim()))}>
          Accept (action needed)
        </button>
        <button type="button" className={btn} disabled={pending || decision.trim().length < 10} onClick={() => run(() => decideNotice(id, false, decision.trim()))}>
          Dismiss
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/** SOURCE-INTAKE-01: the owner stores the exact registered original; the API refuses any other bytes. */
export function UploadOriginal({ id, label }: { id: string; label: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<{ busy: boolean; message: string | null; ok: boolean }>({ busy: false, message: null, ok: false });
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label className="flex items-center gap-2">
        <span>Original PDF for {label}</span>
        <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <button
        type="button"
        className={btn}
        disabled={!file || state.busy}
        onClick={async () => {
          if (!file) return;
          setState({ busy: true, message: "Uploading and checking the checksum…", ok: false });
          try {
            const r = await fetch(`/studio/sources/${id}/original`, { method: "POST", headers: { "Content-Type": "application/pdf" }, body: file });
            const body = (await r.json().catch(() => null)) as { detail?: string; stored?: boolean } | null;
            if (r.ok) setState({ busy: false, ok: true, message: body?.stored ? "Stored. It is the registered original." : "Already stored; nothing changed." });
            else setState({ busy: false, ok: false, message: body?.detail ?? `Upload failed (${r.status}).` });
          } catch {
            setState({ busy: false, ok: false, message: "The connection dropped. Try again." });
          }
        }}
      >
        {state.busy ? "Uploading…" : "Store original"}
      </button>
      {state.message && (
        <span role={state.ok ? "status" : "alert"} className={state.ok ? "text-ok" : "text-danger"}>
          {state.message}
        </span>
      )}
    </div>
  );
}

/** SOURCE-INTAKE-01: open one PDF page of a stored original as an image (new tab). */
export function ViewSourcePage({ id, pages, label }: { id: string; pages: number; label: string }) {
  const [page, setPage] = useState(1);
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label className="flex items-center gap-2">
        <span>PDF page of {label}</span>
        <input type="number" min={1} max={pages} value={page} onChange={(e) => setPage(Number(e.target.value))} className="w-24 rounded-lg border border-border bg-surface px-2 py-1" />
      </label>
      <a href={`/studio/sources/${id}/pages/${Math.min(Math.max(1, page || 1), pages)}`} target="_blank" rel="noopener" className="text-accent underline underline-offset-2">
        View page
      </a>
    </div>
  );
}

/** SOURCE-INTAKE-01: the owner's publication-rights decision, with the evidence it rests on (audited by the API). */
export function RightsForm({ id, label }: { id: string; label: string }) {
  const { error, pending, run } = useAction();
  const [evidence, setEvidence] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const decide = (rights: "CONFIRMED" | "DENIED") =>
    run(() => setPublicationRights(id, rights, evidence), () => setDone(`Recorded: rights ${rights.toLowerCase()}.`));
  return (
    <div className="space-y-1 text-sm">
      <label className="block">
        <span className="block">Evidence for the publication-rights decision on {label}</span>
        <input value={evidence} onChange={(e) => setEvidence(e.target.value)} minLength={10} maxLength={2000} className={field} />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={btn} disabled={pending || evidence.trim().length < 10} onClick={() => decide("CONFIRMED")}>
          Confirm rights
        </button>
        <button type="button" className={btn} disabled={pending || evidence.trim().length < 10} onClick={() => decide("DENIED")}>
          Deny rights
        </button>
      </div>
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
      {done && <p role="status">{done}</p>}
    </div>
  );
}
