"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { endAssistedAccess, startAssistedAccess } from "@/app/actions/support-lookup";

type Props = { userId: string; active: { id: string; expiresAt: string } | null; openRequests: { id: string; label: string }[] };

/** Start or end time-limited assisted access. The learner is told and can end it; every step is recorded. */
export function AssistPanel({ userId, active, openRequests }: Props) {
  const router = useRouter();
  const [ticket, setTicket] = useState(openRequests[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [minutes, setMinutes] = useState(15);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const run = (fn: () => Promise<{ ok: boolean; error?: string }>) =>
    start(async () => {
      setError(null);
      const out = await fn();
      if (out.ok) router.refresh();
      else setError(out.error ?? null);
    });
  return (
    <section aria-labelledby="assist-h" className="space-y-2 rounded-xl border border-border bg-surface-muted p-4">
      <h2 id="assist-h" className="font-semibold">
        Assisted access
      </h2>
      {active ? (
        <button type="button" disabled={pending} onClick={() => run(() => endAssistedAccess(active.id, false))} className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent disabled:opacity-60">
          {pending ? "Ending…" : "End assisted access now"}
        </button>
      ) : openRequests.length === 0 ? (
        <p className="text-sm text-muted">Assisted access needs one of the learner&apos;s open requests.</p>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-muted">Shows result summaries in this timeline for a short time. The learner is told and can end it. Read-only.</p>
          <label htmlFor="assist-ticket" className="block text-sm font-medium">
            For request
          </label>
          <select id="assist-ticket" value={ticket} onChange={(e) => setTicket(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2">
            {openRequests.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
          <label htmlFor="assist-reason" className="block text-sm font-medium">
            Reason (the learner sees this)
          </label>
          <textarea id="assist-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={500} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
          <label htmlFor="assist-minutes" className="block text-sm font-medium">
            For how long
          </label>
          <select id="assist-minutes" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} className="rounded-lg border border-border bg-surface px-3 py-2">
            {[5, 15, 30].map((m) => (
              <option key={m} value={m}>
                {m} minutes
              </option>
            ))}
          </select>
          <div>
            <button
              type="button"
              disabled={pending || reason.trim().length < 10 || !ticket}
              onClick={() => run(() => startAssistedAccess(userId, ticket, reason.trim(), minutes))}
              className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent disabled:opacity-60"
            >
              {pending ? "Starting…" : "Start assisted access"}
            </button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
