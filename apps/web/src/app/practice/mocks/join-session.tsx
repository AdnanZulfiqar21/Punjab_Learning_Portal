"use client";

import { buttonClasses } from "@/components/button";
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
        className={buttonClasses()}
      >
        {pending ? "Joining…" : "Join now"}
      </button>
      {error && (
        <p role="alert" className="rounded-inner border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {error}
        </p>
      )}
    </div>
  );
}
