"use client";

import { useState, useTransition } from "react";
import { accommodate, scheduleSession } from "@/app/actions/exam-profiles";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const btn = "rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent disabled:opacity-60";
const iso = (local: string) => (local ? new Date(local).toISOString() : "");

/** P09.S2.T3: schedule a window for the current published version of a pattern. Times are entered in this browser's local time. */
export function ScheduleSession({ code }: { code: string }) {
  const [v, setV] = useState({ title: "", starts: "", entry: "", closes: "", results: "", late: "fixed_end" });
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [pending, start] = useTransition();
  const input = (k: keyof typeof v, label: string) => (
    <label className="block space-y-1 text-sm">
      <span>{label}</span>
      <input type="datetime-local" value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} className={field} />
    </label>
  );
  return (
    <div className="space-y-2">
      <input aria-label="Session title" placeholder="Title, e.g. October practice mock" value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} className={field} />
      <div className="grid gap-2 sm:grid-cols-2">
        {input("starts", "Starts")}
        {input("entry", "Late entry closes")}
        {input("closes", "Window closes")}
        {input("results", "Results released")}
      </div>
      <select aria-label="Late entry" value={v.late} onChange={(e) => setV({ ...v, late: e.target.value })} className={field}>
        <option value="fixed_end">Fixed end: late entrants get less time</option>
        <option value="full_duration">Full duration from joining, until the window closes</option>
      </select>
      <button
        type="button"
        className={btn}
        disabled={pending || v.title.trim().length < 3 || !v.starts || !v.entry || !v.closes || !v.results}
        onClick={() =>
          start(async () => {
            setError(null);
            const out = await scheduleSession({
              profile_code: code,
              title: v.title.trim(),
              starts_at: iso(v.starts),
              entry_closes_at: iso(v.entry),
              window_closes_at: iso(v.closes),
              results_at: iso(v.results),
              late_entry: v.late,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            });
            if (out.ok) setDone(true);
            else setError(out.error ?? null);
          })
        }
      >
        Schedule this mock
      </button>
      {done && <p className="text-sm">Scheduled. Learners see it under Practice → Mock tests.</p>}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function Accommodation({ sessionId }: { sessionId: string }) {
  const [v, setV] = useState({ email: "", minutes: "15", reason: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="grid gap-2 sm:grid-cols-4">
      <input aria-label="Learner email" placeholder="Learner email" value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} className={field} />
      <input aria-label="Extra minutes" type="number" min={1} max={240} value={v.minutes} onChange={(e) => setV({ ...v, minutes: e.target.value })} className={field} />
      <input aria-label="Accommodation reason" placeholder="Reason (recorded)" value={v.reason} onChange={(e) => setV({ ...v, reason: e.target.value })} className={field} />
      <button
        type="button"
        className={btn}
        disabled={pending || !v.email.trim() || v.reason.trim().length < 10}
        onClick={() =>
          start(async () => {
            const out = await accommodate(sessionId, v.email.trim(), Number(v.minutes), v.reason.trim());
            setMsg(out.ok ? "Extra time recorded." : (out.error ?? "Couldn't record it."));
          })
        }
      >
        Give extra time
      </button>
      {msg && <p className="text-sm sm:col-span-4">{msg}</p>}
    </div>
  );
}
