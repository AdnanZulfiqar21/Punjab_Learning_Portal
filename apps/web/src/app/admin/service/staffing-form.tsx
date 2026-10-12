"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import type { BacklogRow } from "@portal/contracts";
import { setReviewStaffing, type RolloutResult } from "@/app/actions/operations";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const button = "rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

// W06.S3.T2 (STAFFING-01): record the staffing behind a scope's written-review capacity.
export function StaffingForm({ row, label }: { row: BacklogRow; label: string }) {
  const router = useRouter();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RolloutResult | null>(null);
  const s = row.staffing;
  const input = (name: string, text: string, value: number | undefined, max: number) => (
    <div className="space-y-1">
      <label htmlFor={`${id}-${name}`} className="block font-medium">
        {text}
      </label>
      <input id={`${id}-${name}`} name={name} type="number" min={0} max={max} step={1} required defaultValue={value} className={field} />
    </div>
  );
  return (
    <form
      aria-label={`Change review staffing for ${label}`}
      className="grid gap-3 text-sm sm:grid-cols-3"
      action={async (f) => {
        setBusy(true);
        const r = await setReviewStaffing(row.grade, row.subject, f);
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      {input("reviewer_hours_per_week", "Productive marking hours a week", s?.reviewer_hours_per_week, 10000)}
      {input("fixed_hours_per_week", "Fixed obligations (hours a week)", s?.fixed_hours_per_week, 10000)}
      {input("minutes_per_script", "Teacher minutes per script", s?.minutes_per_script, 600)}
      {input("turnaround_days", "Promised turnaround (days)", s?.turnaround_days, 60)}
      {input("max_open_cases", "Case limit", row.max_open_cases, 100000)}
      <div className="space-y-1 sm:col-span-3">
        <label htmlFor={`${id}-reason`} className="block font-medium">
          Reason (recorded in the audit trail)
        </label>
        <input id={`${id}-reason`} name="reason" required minLength={5} maxLength={1000} className={field} />
      </div>
      <div className="sm:col-span-3">
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Saving…" : "Save staffing"}
        </button>
      </div>
      {result && (
        <p role={result.ok ? "status" : "alert"} className={`sm:col-span-3 ${result.ok ? "text-muted" : "text-danger"}`}>
          {result.ok ? "Saved. New written tests are admitted against these figures from now on." : result.error}
        </p>
      )}
    </form>
  );
}
