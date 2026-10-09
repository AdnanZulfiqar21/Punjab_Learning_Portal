"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { AssistedAccess } from "@portal/contracts";
import { endAssistedAccess } from "@/app/actions/support-lookup";

const fmt = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

/** P15.S3.T3: when support had (or has) temporary read-only access to a summary of the learner's activity. */
export function AssistedAccessList({ items, now }: { items: AssistedAccess[]; now: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-2">
      <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Assisted access">
        {items.map((a) => {
          const active = !a.revoked_at && a.expires_at > now;
          return (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm">
              <div>
                <p>{a.reason}</p>
                <p className="text-muted">
                  {fmt(a.granted_at)} · {active ? `until ${fmt(a.expires_at)}` : a.revoked_at ? `ended ${fmt(a.revoked_at)}` : `ended ${fmt(a.expires_at)}`}
                </p>
              </div>
              {active && (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() =>
                    start(async () => {
                      setError(null);
                      const out = await endAssistedAccess(a.id, true);
                      if (out.ok) router.refresh();
                      else setError(out.error ?? null);
                    })
                  }
                  className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent disabled:opacity-60"
                >
                  End now
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
