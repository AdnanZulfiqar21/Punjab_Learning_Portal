"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { runRegrade } from "@/app/actions/adjudication";

// One bounded batch per click; the API checkpoints each attempt, so repeating is always safe.
export function RunRegrade({ id }: { id: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={pending}
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
        onClick={() =>
          start(async () => {
            setError(null);
            const out = await runRegrade(id);
            if (!out.ok) setError(out.error);
            else {
              setNote(`Processed ${out.run.processed} attempt(s); ${out.run.remaining} remaining.`);
              router.refresh();
            }
          })
        }
      >
        {pending ? "Applying…" : "Apply to the next batch"}
      </button>
      {note && (
        <p role="status" className="text-sm">
          {note}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
