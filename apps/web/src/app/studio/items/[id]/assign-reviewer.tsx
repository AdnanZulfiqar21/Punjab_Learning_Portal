"use client";

// P06.S1.T2 (ASSIGN-REVIEWER-01): a publisher assigns who reviews this item, from the eligible reviewers the server
// lists, or clears the assignment. The server re-checks scope, independence and that the account is active.
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { assignReviewer } from "@/app/actions/studio";

export function AssignReviewer({
  itemId,
  assigned,
  options,
}: {
  itemId: string;
  assigned: string | null;
  options: { id: string; email: string }[];
}) {
  const router = useRouter();
  const [choice, setChoice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const run = (reviewerId: string | null) =>
    start(async () => {
      setError(null);
      const out = await assignReviewer(itemId, reviewerId);
      if (out.ok) {
        setChoice("");
        router.refresh();
      } else setError(out.error ?? "The assignment wasn't saved.");
    });
  return (
    <section aria-labelledby="assign-h" className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
      <h2 id="assign-h" className="font-semibold">
        Reviewer
      </h2>
      <p className="text-muted">{assigned ? `Assigned to ${assigned}.` : "Nobody is assigned: any eligible reviewer can claim it."}</p>
      {options.length === 0 ? (
        <p className="text-muted">No one else can review this: no active reviewer for this class and subject who didn&apos;t edit it.</p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="space-y-1">
            <span className="block font-medium">Assign to</span>
            <select value={choice} onChange={(e) => setChoice(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2">
              <option value="">Choose a reviewer…</option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.email}
                </option>
              ))}
            </select>
          </label>
          <button type="button" disabled={pending || !choice} onClick={() => run(choice)} className="rounded-lg bg-accent px-4 py-2 font-medium text-white disabled:opacity-60 dark:text-background">
            Assign
          </button>
          {assigned && (
            <button type="button" disabled={pending} onClick={() => run(null)} className="rounded-lg border border-border px-4 py-2 font-medium disabled:opacity-60">
              Clear the assignment
            </button>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
