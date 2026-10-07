"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { WrittenResult } from "@portal/contracts";
import { requestRecheck } from "@/app/actions/support";
import { Notice } from "@/components/ui";

const date = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

// Learners may ask once, inside the window, for named questions to be marked again by a different teacher. A recheck
// never consumes another written allowance, and every released version stays visible below.
export function RecheckPanel({ attemptId, result, marks }: { attemptId: string; result: WrittenResult; marks: (u: number) => string }) {
  const router = useRouter();
  const [picked, setPicked] = useState<number[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const rc = result.recheck;
  return (
    <div className="space-y-3">
      {result.history.length > 1 && (
        <div className="rounded-lg bg-surface-muted p-3 text-sm">
          <p className="font-semibold">Mark history</p>
          <ul>
            {result.history.map((h) => (
              <li key={h.version}>
                Version {h.version}: {marks(h.total_units)} · {h.case_kind === "recheck" ? "after recheck" : "first marking"} · released {date(h.released_at)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {rc.status === "requested" && <Notice title="Recheck requested">A different teacher will look at the questions you named. Your new marks will appear here.</Notice>}
      {rc.status === "closed" && <p className="text-sm text-muted">The recheck window for this test has closed.</p>}
      {rc.status === "available" && (
        <details className="rounded-xl border border-border bg-surface p-4">
          <summary className="cursor-pointer font-medium">Ask for a recheck</summary>
          <div className="mt-3 space-y-3">
            <p className="text-sm text-muted">
              A different teacher will mark the questions you choose again. Marks can go up or down.{" "}
              {rc.window_ends_at && <>You can ask until {date(rc.window_ends_at)}.</>}
            </p>
            <fieldset className="space-y-1">
              <legend className="font-medium">Which questions?</legend>
              {result.questions.map((q) => (
                <label key={q.position} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={picked.includes(q.position)}
                    onChange={(e) => setPicked((p) => (e.target.checked ? [...p, q.position].sort((a, b) => a - b) : p.filter((x) => x !== q.position)))}
                  />
                  Question {q.position}
                </label>
              ))}
            </fieldset>
            <div className="space-y-1">
              <label htmlFor="recheck-reason" className="font-medium">
                Why should it be marked again?
              </label>
              <textarea id="recheck-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} minLength={10} maxLength={2000} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
            </div>
            {error && (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            )}
            <button
              type="button"
              disabled={pending || picked.length === 0 || reason.trim().length < 10}
              onClick={() =>
                start(async () => {
                  const out = await requestRecheck(attemptId, picked, reason.trim());
                  if (out.ok) router.refresh();
                  else setError(out.error ?? null);
                })
              }
              className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
            >
              {pending ? "Sending…" : "Request recheck"}
            </button>
          </div>
        </details>
      )}
    </div>
  );
}
