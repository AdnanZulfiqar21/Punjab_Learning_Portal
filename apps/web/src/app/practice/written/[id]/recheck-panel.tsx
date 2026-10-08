"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { WrittenResult } from "@portal/contracts";
import { requestRecheck } from "@/app/actions/support";
import { Notice } from "@/components/ui";

const HISTORY_LABEL: Record<string, string> = {
  initial: "first marking",
  recheck: "after recheck",
  completion: "after completing pending questions",
  regrade: "after a marking-guide correction",
};
const date = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

// Learners may ask once, inside the window, for named questions to be marked again by a different teacher. A recheck
// never consumes another written allowance, and every released version stays visible below.
export function RecheckPanel({ attemptId, result, marks }: { attemptId: string; result: WrittenResult; marks: (u: number) => string }) {
  const router = useRouter();
  const [picked, setPicked] = useState<number[]>([]);
  const [criteria, setCriteria] = useState<Record<string, string[]>>({});
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
                Version {h.version}: {marks(h.total_units)} · {HISTORY_LABEL[h.case_kind] ?? h.case_kind} · released {date(h.released_at)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {rc.status === "requested" && (
        <Notice title="Recheck requested">
          A different teacher will look at question{rc.positions.length > 1 ? "s" : ""} {rc.positions.join(", ")}. Your other marks stay as they are. New marks
          will appear here.
        </Notice>
      )}
      {rc.status === "closed" && (
        <p className="text-sm text-muted">
          {rc.closed_reason === "window_ended"
            ? "The recheck window for these marks has closed."
            : "These marks have already been rechecked. Only questions changed by a later correction can be appealed."}
        </p>
      )}
      {rc.status === "available" && (
        <details className="rounded-xl border border-border bg-surface p-4">
          <summary className="cursor-pointer font-medium">Ask for a recheck</summary>
          <div className="mt-3 space-y-3">
            <p className="text-sm text-muted">
              A different teacher will mark the questions you choose again. Marks can go up or down, and your other questions keep
              their marks.{" "}
              {rc.target_version !== null && result.history.length > 1 && <>This appeal is about the corrected marks (version {rc.target_version}). </>}
              {rc.window_ends_at && <>You can ask until {date(rc.window_ends_at)}.</>}
            </p>
            <fieldset className="space-y-1">
              <legend className="font-medium">Which questions?</legend>
              {result.questions
                .filter((q) => rc.eligible_positions.includes(q.position))
                .map((q) => (
                  <div key={q.position} className="space-y-1">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={picked.includes(q.position)}
                        onChange={(e) => setPicked((p) => (e.target.checked ? [...p, q.position].sort((a, b) => a - b) : p.filter((x) => x !== q.position)))}
                      />
                      Question {q.position}
                    </label>
                    {picked.includes(q.position) && q.criteria.length > 1 && (
                      <fieldset className="ml-6 space-y-1 text-sm">
                        <legend className="text-muted">Which part? (optional)</legend>
                        {q.criteria.map((c) => {
                          const key = String(q.position);
                          const on = criteria[key]?.includes(c.id) ?? false;
                          return (
                            <label key={c.id} className="flex items-start gap-2">
                              <input
                                type="checkbox"
                                checked={on}
                                onChange={(e) =>
                                  setCriteria((all) => ({
                                    ...all,
                                    [key]: e.target.checked ? [...(all[key] ?? []), c.id] : (all[key] ?? []).filter((x) => x !== c.id),
                                  }))
                                }
                              />
                              <span>{c.description}</span>
                            </label>
                          );
                        })}
                      </fieldset>
                    )}
                  </div>
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
                  const chosen = Object.fromEntries(Object.entries(criteria).filter(([k, v]) => picked.includes(Number(k)) && v.length));
                  const out = await requestRecheck(attemptId, picked, reason.trim(), chosen);
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
