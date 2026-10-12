"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { adjudicateComparison, type CalibrationResult } from "@/app/actions/calibration";

const VERDICTS: [string, string][] = [
  ["teacher", "The teacher applied the rubric correctly"],
  ["proposal", "The proposal applied the rubric correctly"],
  ["both", "Both are acceptable readings"],
  ["neither", "Neither applied it correctly"],
];

// CALIBRATION-01: one verdict per disputed criterion, with a reason. Recorded for the reliability review only.
export function AdjudicateComparison({ id, criteria }: { id: string; criteria: string[] }) {
  const router = useRouter();
  const uid = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CalibrationResult | null>(null);
  return (
    <form
      aria-label="Record verdicts"
      className="space-y-2"
      action={async (f) => {
        setBusy(true);
        const r = await adjudicateComparison(
          id,
          Object.fromEntries(criteria.map((c) => [c, String(f.get(`verdict-${c}`) ?? "")])),
          String(f.get("reason") ?? "").trim(),
        );
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      {criteria.map((c) => (
        <label key={c} className="flex flex-wrap items-center gap-2">
          <span className="font-mono">{c}</span>
          <select name={`verdict-${c}`} required className="rounded-lg border border-border bg-surface px-2 py-1">
            {VERDICTS.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ))}
      <label htmlFor={`${uid}-reason`} className="block font-medium">
        Reason (recorded in the audit trail)
      </label>
      <textarea id={`${uid}-reason`} name="reason" required minLength={10} maxLength={2000} rows={2} className="w-full rounded-lg border border-border bg-surface px-2 py-1" />
      <button type="submit" disabled={busy} className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
        {busy ? "Saving…" : "Record verdicts"}
      </button>
      {result && !result.ok && (
        <p role="alert" className="text-danger">
          {result.error}
        </p>
      )}
    </form>
  );
}
