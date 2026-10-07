"use client";

import { useState, useTransition } from "react";
import { createRubric } from "@/app/actions/studio";

/** Start a marking rubric for this written question (a question can't be published without one). */
export function AddRubric({ questionId, title }: { questionId: string; title: string }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface-muted px-4 py-3 text-sm">
      <span>Written questions are published only with a reviewed marking rubric for the same version.</span>
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          start(async () => {
            const out = await createRubric(questionId, title);
            if (out?.error) setError(out.error);
          })
        }
        className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent disabled:opacity-60"
      >
        {pending ? "Creating…" : "Add a marking rubric"}
      </button>
      {error && (
        <span role="alert" className="text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
