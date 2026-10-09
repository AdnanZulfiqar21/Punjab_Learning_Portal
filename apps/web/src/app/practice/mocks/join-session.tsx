"use client";

import { useState, useTransition } from "react";
import { joinSession } from "@/app/actions/practice";

export function JoinSession({ id }: { id: string }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-1">
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          start(async () => {
            const out = await joinSession(id);
            if (out?.error) setError(out.error);
          })
        }
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Joining…" : "Join now"}
      </button>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
