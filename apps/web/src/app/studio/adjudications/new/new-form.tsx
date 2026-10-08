"use client";

import { useActionState } from "react";
import { createAdjudication, type AdjudicationFormState } from "@/app/actions/adjudication";

export function NewAdjudicationForm({ rubricId }: { rubricId: string }) {
  const [state, action, pending] = useActionState<AdjudicationFormState, FormData>(createAdjudication, undefined);
  return (
    <form action={action} className="space-y-3">
      <input type="hidden" name="rubric_item_id" value={rubricId} />
      <label className="block space-y-1">
        <span className="font-medium">Why does this correction apply to work already marked?</span>
        <textarea name="reason" required minLength={20} maxLength={2000} rows={4} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
      </label>
      {state?.active && state.active.length > 0 && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="supersedes_id" value={state.active[0]} />
          Replace the active correction for these versions (it stops applying; this one is applied instead)
        </label>
      )}
      {state?.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Applying…" : "Approve and preview the impact"}
      </button>
    </form>
  );
}
