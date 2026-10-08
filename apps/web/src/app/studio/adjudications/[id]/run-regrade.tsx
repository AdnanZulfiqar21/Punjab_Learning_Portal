"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import type { RegradeJob } from "@portal/contracts";
import { queueRegrade, regradeJob, retryRegrade } from "@/app/actions/adjudication";

const LABEL: Record<string, string> = {
  queued: "Queued for the worker",
  running: "Running",
  succeeded: "Finished",
  failed: "Finished with failures",
  superseded: "Stopped: the correction was superseded",
};

// W06-06: applying queues a durable job; the worker processes it in bounded batches. This polls its progress.
export function RunRegrade({ id, initialJob }: { id: string; initialJob: RegradeJob | null }) {
  const router = useRouter();
  const [job, setJob] = useState<RegradeJob | null>(initialJob);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const live = job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (!job || !live) return;
    const t = setTimeout(async () => {
      const out = await regradeJob(job.id);
      if (out.ok) {
        setJob(out.job);
        if (out.job.status !== "queued" && out.job.status !== "running") router.refresh();
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [job, live, router]);

  const act = (fn: () => ReturnType<typeof queueRegrade>) =>
    start(async () => {
      setError(null);
      const out = await fn();
      if (out.ok) setJob(out.job);
      else setError(out.error);
    });

  return (
    <section aria-label="Apply the correction" className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={pending || live}
          onClick={() => act(() => queueRegrade(id))}
          className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
        >
          {live ? "Applying…" : "Apply to submitted scripts"}
        </button>
        {job?.status === "failed" && (
          <button type="button" disabled={pending} onClick={() => act(() => retryRegrade(job.id))} className="rounded-lg border border-border px-4 py-2 font-medium">
            Retry failed scripts
          </button>
        )}
      </div>
      {job && (
        <p role="status" className="text-sm">
          {LABEL[job.status] ?? job.status}: {job.processed} processed ({job.regraded} regraded, {job.unaffected} unaffected), {job.failed} failed
          {job.remaining !== null && job.remaining !== undefined ? `, ${job.remaining} remaining` : ""}
          {job.last_error ? ` · last error: ${job.last_error}` : ""}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
