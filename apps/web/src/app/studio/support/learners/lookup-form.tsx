"use client";

import { useActionState } from "react";
import { lookUpLearner, type LookupState } from "@/app/actions/support-lookup";

export function LookupForm() {
  const [state, action, pending] = useActionState<LookupState, FormData>(lookUpLearner, undefined);
  return (
    <form action={action} className="space-y-2">
      <label htmlFor="lookup-email" className="font-medium">
        Learner&apos;s email
      </label>
      <div className="flex flex-wrap gap-2">
        <input id="lookup-email" name="email" type="email" required maxLength={320} autoComplete="off" className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2" />
        <button type="submit" disabled={pending} className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
          {pending ? "Looking…" : "Look up"}
        </button>
      </div>
      {state?.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
    </form>
  );
}
