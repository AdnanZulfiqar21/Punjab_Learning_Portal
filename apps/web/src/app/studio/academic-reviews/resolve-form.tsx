"use client";

import { useActionState, useState } from "react";
import { resolveAcademicReview, type ResolveState } from "@/app/actions/academic-review";

// ACADEMIC-REVIEW-01: the decision never sets a mark. "Guide corrected" names an approved correction of this
// question's marking guide; "guide stands" keeps it. Either way a teacher then marks the question as usual.
export function ResolveForm({ reviewId, corrections }: { reviewId: string; corrections: { id: string; label: string }[] }) {
  const [state, action, pending] = useActionState<ResolveState, FormData>(resolveAcademicReview, undefined);
  const [resolution, setResolution] = useState<"not_covered" | "guide_corrected">("not_covered");
  if (state?.done) return <p role="status" className="text-sm font-medium">Decided. The question can now be marked.</p>;
  return (
    <form action={action} className="space-y-3 border-t border-border pt-3 text-sm">
      <input type="hidden" name="review_id" value={reviewId} />
      <fieldset className="space-y-1">
        <legend className="font-medium">Decision</legend>
        <label className="flex items-center gap-2">
          <input type="radio" name="resolution" value="not_covered" checked={resolution === "not_covered"} onChange={() => setResolution("not_covered")} />
          The guide stands: mark the question under it
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="resolution"
            value="guide_corrected"
            checked={resolution === "guide_corrected"}
            disabled={corrections.length === 0}
            onChange={() => setResolution("guide_corrected")}
          />
          An approved correction of the guide now covers the method
          {corrections.length === 0 && <span className="text-muted">(none approved for this guide yet)</span>}
        </label>
      </fieldset>
      {resolution === "guide_corrected" && (
        <label className="block space-y-1">
          <span className="font-medium">Which correction?</span>
          <select name="adjudication_id" required className="w-full rounded-lg border border-border bg-surface px-3 py-2">
            {corrections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="block space-y-1">
        <span className="font-medium">Why (kept on the record and shown to the marker)</span>
        <textarea name="note" required minLength={10} maxLength={2000} rows={2} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
      </label>
      {state?.error && (
        <p role="alert" className="text-danger">
          {state.error}
        </p>
      )}
      <button type="submit" disabled={pending} className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
        {pending ? "Saving…" : "Record the decision"}
      </button>
    </form>
  );
}
