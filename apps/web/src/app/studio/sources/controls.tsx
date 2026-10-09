"use client";

import { useState, useTransition } from "react";
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
          <option value="11">Class XI</option>
          <option value="12">Class XII</option>
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
