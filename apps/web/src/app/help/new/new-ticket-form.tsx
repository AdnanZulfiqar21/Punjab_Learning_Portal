"use client";

import { useActionState } from "react";
import { createTicket, type TicketFormState } from "@/app/actions/support";

const CATEGORIES: [string, string][] = [
  ["account", "My account or sign-in"],
  ["access", "My plan or free trial"],
  ["technical", "Something isn't working"],
  ["academic_report", "A mistake in a question"],
  ["other", "Something else"],
];
const field = "w-full rounded-lg border border-border bg-surface px-3 py-2.5";

export function NewTicketForm({ category, refKind, refId, refPosition }: { category: string; refKind: string; refId: string; refPosition: string }) {
  const [state, action, pending] = useActionState<TicketFormState, FormData>(createTicket, undefined);
  const isReport = category === "academic_report" && refKind && refId && refPosition;
  return (
    <form action={action} className="space-y-5">
      <input type="hidden" name="ref_kind" value={refKind} />
      <input type="hidden" name="ref_id" value={refId} />
      <input type="hidden" name="ref_position" value={refPosition} />
      {isReport ? (
        <>
          <input type="hidden" name="category" value="academic_report" />
          <p className="rounded-lg bg-surface-muted px-3 py-2 text-sm">
            You&apos;re reporting question {refPosition} from your test. A subject reviewer will check it against the textbook.
          </p>
        </>
      ) : (
        <div className="space-y-1">
          <label htmlFor="category" className="font-medium">
            What is it about?
          </label>
          <select id="category" name="category" defaultValue={category === "academic_report" ? "technical" : category} className={field}>
            {CATEGORIES.filter(([v]) => v !== "academic_report").map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="space-y-1">
        <label htmlFor="subject" className="font-medium">
          Summary
        </label>
        <input id="subject" name="subject" required minLength={3} maxLength={200} defaultValue={isReport ? `Question ${refPosition} may be wrong` : ""} className={field} />
      </div>
      <div className="space-y-1">
        <label htmlFor="body" className="font-medium">
          Details
        </label>
        <textarea id="body" name="body" required minLength={5} maxLength={4000} rows={6} className={field} placeholder={isReport ? "What seems wrong? For example the key, the wording, a unit or a diagram." : "What happened, and what did you expect?"} />
        <p className="text-sm text-muted">Please don&apos;t include passwords or payment card numbers.</p>
      </div>
      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
        </p>
      )}
      <button type="submit" disabled={pending} className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
        {pending ? "Sending…" : "Send"}
      </button>
    </form>
  );
}
