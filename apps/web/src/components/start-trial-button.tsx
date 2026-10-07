"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { startTrial } from "@/app/actions/access";

export function StartTrialButton() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          start(async () => {
            const out = await startTrial();
            if (out.ok) router.refresh();
            else setError(out.error);
          })
        }
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Starting…" : "Start my free 30-day trial"}
      </button>
      {error && (
        <span role="alert" className="ml-3 text-danger">
          {error}
        </span>
      )}
    </>
  );
}
